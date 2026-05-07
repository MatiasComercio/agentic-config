#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run a programmatic pi worker behind a file-based MUX-compatible contract."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Sequence, TextIO

DEFAULT_STARTUP_WARN_AFTER_SECONDS = 30.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 5.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 60.0
DEFAULT_HANG_SNAPSHOT_AFTER_SECONDS = 120.0
DEFAULT_RUNTIME_TIMEOUT_SECONDS = 0.0
DEFAULT_IDLE_TIMEOUT_SECONDS = 0.0
DEFAULT_TOOL_ALLOWLIST = "read,bash,edit,write,grep,find,ls"
MAX_SESSION_TAIL_BYTES = 262_144
MAX_SESSION_TAIL_LINES = 80
# Do not import stdlib signal here: this directory also contains signal.py.
SIGTERM = 15
SIGKILL = 9
SENSITIVE_PROCESS_ARG_FLAGS = frozenset(
    {
        "-p",
        "--api-key",
        "--system-prompt",
        "--append-system-prompt",
    }
)
SENSITIVE_PROCESS_ARG_PREFIXES = tuple(sorted(SENSITIVE_PROCESS_ARG_FLAGS, key=len, reverse=True))
EVENT_REDACT_KEYS = frozenset(
    {
        "args",
        "arguments",
        "assistantMessageEvent",
        "command",
        "content",
        "cwd",
        "diff",
        "encryptedContent",
        "encrypted_content",
        "input",
        "message",
        "messages",
        "output",
        "partial",
        "patch",
        "prompt",
        "result",
        "results",
        "stderr",
        "stdout",
        "text",
        "thinking",
        "thinkingSignature",
        "toolInput",
        "toolOutput",
    }
)
EVENT_REDACT_KEY_FRAGMENTS = ("authorization", "encrypted", "password", "secret", "signature", "token")
MAX_EVENT_STRING_CHARS = 240
MAX_EVENT_ARRAY_ITEMS = 12

REQUIRED_REPORT_HEADINGS = (
    "## Table of Contents",
    "## Executive Summary",
    "### Next Steps",
)


class PiBashError(RuntimeError):
    """Raised when the pi-bash wrapper cannot complete safely."""


@dataclass(frozen=True)
class ResolvedSkill:
    """Resolved skill preload metadata."""

    requested: str
    cli_path: Path
    content_path: Path
    content_sha256: str


@dataclass(frozen=True)
class ProcessSnapshot:
    """Sanitized process metadata for startup diagnostics."""

    pid: int
    ppid: int
    stat: str
    etime: str
    command: str


@dataclass
class OutputActivity:
    """Thread-safe child-output activity tracker."""

    last_output_monotonic: float
    lock: Lock

    def mark(self) -> None:
        """Record child stdout/stderr activity."""
        with self.lock:
            self.last_output_monotonic = time.monotonic()

    def idle_seconds(self) -> float:
        """Return seconds since the last child stdout/stderr activity."""
        with self.lock:
            return time.monotonic() - self.last_output_monotonic


@dataclass(frozen=True)
class LaunchPaths:
    """Attempt-scoped worker log and manifest paths."""

    stdout_log: Path
    stderr_log: Path
    events_log: Path
    raw_events_log: Path
    wrapper_log: Path
    latest_manifest: Path


@dataclass(frozen=True)
class LaunchConfig:
    """Validated launch configuration."""

    session_dir: str
    agent_id: str
    role: str
    worker_type: str | None
    objective: str
    scope: str
    task: str
    report_path: str
    signal_path: str
    model: str
    thinking: str | None
    skills: tuple[str, ...]
    extensions: tuple[str, ...]
    allow_extensions: bool
    tools: str | None
    stream: bool
    raw_events: bool
    startup_warn_after: float
    shutdown_timeout: float
    mirror_prefix: str | None
    heartbeat_interval: float
    hang_snapshot_after: float
    runtime_timeout: float
    idle_timeout: float
    attempt_id: str
    cwd: Path
    pi_bin: str


def main(argv: Sequence[str] | None = None) -> int:
    """Run the pi-bash CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "launch":
            return launch_from_args(args)
        raise PiBashError(f"unsupported command: {args.command}")
    except PiBashError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    launch_parser = subparsers.add_parser("launch", help="launch a supervised pi worker")
    launch_parser.add_argument("session_dir", help="Project-root-relative or absolute mux/session directory")
    launch_parser.add_argument("agent_id", help="Opaque worker identifier used for log filenames")
    launch_parser.add_argument("--role", required=True, help="Project-defined opaque role label")
    launch_parser.add_argument("--worker-type", default=None, help="Optional orchestration worker type")
    launch_parser.add_argument("--objective", required=True, help="Declared worker objective")
    launch_parser.add_argument("--scope", required=True, help="Declared worker scope")
    launch_parser.add_argument("--task", required=True, help="Bounded worker task instructions")
    launch_parser.add_argument("--report-path", required=True, help="Required worker report path")
    launch_parser.add_argument("--signal-path", required=True, help="Required success signal path")
    launch_parser.add_argument("--model", required=True, help="pi model argument to pass through")
    launch_parser.add_argument("--thinking", default=None, help="Optional pi thinking level to pass through")
    launch_parser.add_argument(
        "--skill",
        action="append",
        default=[],
        help="Skill name or path to preload; repeat to preserve order",
    )
    launch_parser.add_argument(
        "--extension",
        action="append",
        default=[],
        help="Explicit pi extension path to load; repeat to preserve order",
    )
    launch_parser.add_argument(
        "--allow-extensions",
        action="store_true",
        help="Allow normal extension discovery; default is --no-extensions plus explicit --extension only",
    )
    launch_parser.add_argument(
        "--tools",
        default=DEFAULT_TOOL_ALLOWLIST,
        help="Comma-separated pi tool allowlist; use an empty value to omit the flag",
    )
    launch_parser.add_argument("--stream", action="store_true", help="Stream lean pi JSON events to stderr and an events log")
    launch_parser.add_argument(
        "--raw-events",
        action="store_true",
        help="In stream mode, additionally persist unsanitized child stdout to logs/<agent-id>.raw-events.jsonl",
    )
    launch_parser.add_argument(
        "--startup-warn-after",
        type=parse_non_negative_float,
        default=DEFAULT_STARTUP_WARN_AFTER_SECONDS,
        help="Seconds to wait in stream mode for first child stdout/stderr before warning; use 0 to disable",
    )
    launch_parser.add_argument(
        "--mirror-prefix",
        default="pi> ",
        help="Prefix for live mirrored child output in stream mode",
    )
    launch_parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="Disable live child output mirroring; logs and events are still captured",
    )
    launch_parser.add_argument(
        "--shutdown-timeout",
        type=parse_non_negative_float,
        default=DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
        help="Seconds to wait for stream reader threads to drain after child exit before cleaning up descendants",
    )
    launch_parser.add_argument(
        "--heartbeat-interval",
        type=parse_non_negative_float,
        default=DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        help="Seconds between wrapper heartbeat diagnostics while the child is still running; use 0 to disable",
    )
    launch_parser.add_argument(
        "--hang-snapshot-after",
        type=parse_non_negative_float,
        default=DEFAULT_HANG_SNAPSHOT_AFTER_SECONDS,
        help="Seconds before heartbeats include process/session snapshots; use 0 to disable snapshots",
    )
    launch_parser.add_argument(
        "--runtime-timeout",
        type=parse_non_negative_float,
        default=DEFAULT_RUNTIME_TIMEOUT_SECONDS,
        help="Maximum child runtime in seconds before terminating; use 0 to disable",
    )
    launch_parser.add_argument(
        "--idle-timeout",
        type=parse_non_negative_float,
        default=DEFAULT_IDLE_TIMEOUT_SECONDS,
        help="Maximum seconds without child stdout/stderr before terminating; use 0 to disable",
    )
    launch_parser.add_argument("--attempt-id", default=None, help="Optional deterministic attempt id for log names")
    launch_parser.add_argument("--cwd", default=".", help="Project root / worker current directory")
    launch_parser.add_argument("--pi-bin", default="pi", help="pi executable path, primarily for tests")
    return parser


def parse_non_negative_float(value: str) -> float:
    """Parse a non-negative float command-line argument."""
    try:
        amount = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"expected a number, got {value!r}") from error
    if amount < 0:
        raise argparse.ArgumentTypeError(f"expected a non-negative number, got {value!r}")
    return amount


def launch_from_args(args: argparse.Namespace) -> int:
    """Validate arguments, launch pi, and validate the file protocol."""
    config = parse_launch_config(args)
    resolved_skills = tuple(resolve_skill(config.cwd, skill) for skill in config.skills)
    prompt = build_worker_prompt(config, resolved_skills)
    paths = log_paths(config.cwd, config.session_dir, config.agent_id, config.attempt_id)
    report_abs = resolve_project_path(config.cwd, config.report_path)
    signal_abs = resolve_project_path(config.cwd, config.signal_path)
    clear_previous_artifacts(report_abs=report_abs, signal_abs=signal_abs)

    result: int | None = None
    lifecycle_error: PiBashError | None = None
    try:
        result = run_pi(config, resolved_skills, prompt, paths, report_abs, signal_abs)
    except PiBashError as error:
        lifecycle_error = error

    try:
        validate_protocol_outputs(
            report_abs=report_abs,
            signal_abs=signal_abs,
            report_path_arg=config.report_path,
            cwd=config.cwd,
        )
    except PiBashError as protocol_error:
        details: list[str] = []
        if result is not None and result != 0:
            details.append(f"pi exited with code {result}")
        if lifecycle_error is not None:
            details.append(f"wrapper lifecycle error: {lifecycle_error}")
        suffix = f"; {'; '.join(details)}" if details else ""
        raise PiBashError(f"{protocol_error}{suffix}; see {paths.stdout_log} and {paths.stderr_log}") from protocol_error

    if (result is not None and result != 0) or lifecycle_error is not None:
        record_protocol_success_diagnostic(
            stderr_log=paths.stderr_log,
            wrapper_log=paths.wrapper_log,
            result=result,
            lifecycle_error=lifecycle_error,
        )
    sys.stdout.write("0")
    return 0


def parse_launch_config(args: argparse.Namespace) -> LaunchConfig:
    """Convert parsed argparse values into a validated launch config."""
    cwd = Path(os.path.expandvars(str(args.cwd))).expanduser()
    if not cwd.is_absolute():
        cwd = Path.cwd() / cwd
    cwd = cwd.resolve(strict=False)
    if not cwd.exists() or not cwd.is_dir():
        raise PiBashError(f"cwd does not exist or is not a directory: {cwd}")

    required_values = {
        "session_dir": args.session_dir,
        "agent_id": args.agent_id,
        "role": args.role,
        "objective": args.objective,
        "scope": args.scope,
        "task": args.task,
        "report_path": args.report_path,
        "signal_path": args.signal_path,
        "model": args.model,
    }
    for name, value in required_values.items():
        if not str(value).strip():
            raise PiBashError(f"{name} is required")

    return LaunchConfig(
        session_dir=str(args.session_dir),
        agent_id=str(args.agent_id),
        role=str(args.role),
        worker_type=str(args.worker_type) if args.worker_type else None,
        objective=str(args.objective),
        scope=str(args.scope),
        task=str(args.task),
        report_path=str(args.report_path),
        signal_path=str(args.signal_path),
        model=str(args.model),
        thinking=str(args.thinking) if args.thinking else None,
        skills=tuple(str(skill) for skill in args.skill),
        extensions=tuple(str(extension) for extension in args.extension),
        allow_extensions=bool(args.allow_extensions),
        tools=str(args.tools) if str(args.tools).strip() else None,
        stream=bool(args.stream),
        raw_events=bool(args.raw_events),
        startup_warn_after=float(args.startup_warn_after),
        shutdown_timeout=float(args.shutdown_timeout),
        mirror_prefix=None if args.no_mirror else str(args.mirror_prefix),
        heartbeat_interval=float(args.heartbeat_interval),
        hang_snapshot_after=float(args.hang_snapshot_after),
        runtime_timeout=float(args.runtime_timeout),
        idle_timeout=float(args.idle_timeout),
        attempt_id=str(args.attempt_id) if args.attempt_id else build_attempt_id(),
        cwd=cwd,
        pi_bin=str(args.pi_bin),
    )


def run_pi(
    config: LaunchConfig,
    skills: Sequence[ResolvedSkill],
    prompt: str,
    paths: LaunchPaths,
    report_abs: Path,
    signal_abs: Path,
) -> int:
    """Run the underlying pi process and persist raw output to attempt-scoped logs."""
    paths.stdout_log.parent.mkdir(parents=True, exist_ok=True)
    paths.stderr_log.parent.mkdir(parents=True, exist_ok=True)
    paths.events_log.parent.mkdir(parents=True, exist_ok=True)

    command = build_pi_command(config, skills, prompt)
    write_launch_metadata(
        wrapper_log=paths.wrapper_log,
        config=config,
        command=command,
        prompt=prompt,
        skill_count=len(skills),
        paths=paths,
    )
    write_latest_manifest(paths, config, command, "prepared")
    if not config.stream and paths.raw_events_log.exists():
        paths.raw_events_log.unlink()
    if config.stream:
        return run_streaming_pi(command, config, paths, report_abs, signal_abs)
    return run_non_streaming_pi(command, config, paths, report_abs, signal_abs)


def build_pi_command(config: LaunchConfig, skills: Sequence[ResolvedSkill], prompt: str) -> list[str]:
    """Build the shell-free pi argv."""
    command = [config.pi_bin]
    if config.stream:
        command.extend(["--mode", "json"])
    if not config.allow_extensions:
        command.append("--no-extensions")
    for extension in config.extensions:
        command.extend(["--extension", extension])
    if config.tools:
        command.extend(["--tools", config.tools])
    command.extend(["--model", config.model])
    if config.thinking:
        command.extend(["--thinking", config.thinking])
    for skill in skills:
        command.extend(["--skill", str(skill.cli_path)])
    command.extend(["-p", prompt])
    return command


def run_streaming_pi(
    command: Sequence[str],
    config: LaunchConfig,
    paths: LaunchPaths,
    report_abs: Path,
    signal_abs: Path,
) -> int:
    """Run pi in JSON stream mode with supervised diagnostics."""
    process = spawn_pi_process(command, config, paths)
    if process.stdout is None or process.stderr is None:
        terminate_process_group(process, config.shutdown_timeout, paths.wrapper_log)
        raise PiBashError("failed to capture pi stdout/stderr")

    stderr_lock = Lock()
    first_output = Event()
    activity = OutputActivity(last_output_monotonic=time.monotonic(), lock=Lock())
    if not config.raw_events and paths.raw_events_log.exists():
        paths.raw_events_log.unlink()
    raw_events_file: TextIO | None = None
    with paths.stdout_log.open("w", encoding="utf-8", buffering=1) as stdout_file, paths.stderr_log.open(
        "w",
        encoding="utf-8",
        buffering=1,
    ) as stderr_file, paths.events_log.open("w", encoding="utf-8", buffering=1) as events_file:
        stdout_file.write(stream_stdout_notice(paths.events_log, paths.raw_events_log if config.raw_events else None))
        stdout_file.flush()
        emit_wrapper_diagnostic(spawn_notice(process, config, paths), stderr_file, stderr_lock, paths.wrapper_log)
        if config.raw_events:
            raw_events_file = paths.raw_events_log.open("w", encoding="utf-8", buffering=1)
        try:
            stdout_thread = Thread(
                target=tee_stdout_stream,
                args=(
                    process.stdout,
                    stdout_file,
                    events_file,
                    raw_events_file,
                    stderr_lock,
                    first_output,
                    activity,
                    config.mirror_prefix,
                ),
                daemon=True,
            )
            stderr_thread = Thread(
                target=tee_stderr_stream,
                args=(process.stderr, (stderr_file,), stderr_lock, first_output, activity, config.mirror_prefix),
                daemon=True,
            )
            threads = (stdout_thread, stderr_thread)
            stdout_thread.start()
            stderr_thread.start()
            try:
                emit_startup_warning_if_silent(
                    process=process,
                    first_output=first_output,
                    startup_warn_after=config.startup_warn_after,
                    stderr_file=stderr_file,
                    stderr_lock=stderr_lock,
                    wrapper_log=paths.wrapper_log,
                )
                return_code = wait_for_supervised_process(
                    process=process,
                    config=config,
                    paths=paths,
                    report_abs=report_abs,
                    signal_abs=signal_abs,
                    stderr_file=stderr_file,
                    stderr_lock=stderr_lock,
                    activity=activity,
                )
                ensure_stream_threads_finished(process, threads, config, paths, stderr_file, stderr_lock)
            except Exception:
                if process.poll() is None:
                    terminate_process_group(process, config.shutdown_timeout, paths.wrapper_log)
                join_stream_threads(threads, config.shutdown_timeout)
                raise
        finally:
            if raw_events_file is not None:
                raw_events_file.close()
    append_wrapper_log(paths.wrapper_log, f"completed_at: {utc_timestamp()}\nexit_code: {return_code}\n")
    write_latest_manifest(paths, config, command, "completed", child_pid=process.pid, exit_code=return_code)
    return return_code


def run_non_streaming_pi(
    command: Sequence[str],
    config: LaunchConfig,
    paths: LaunchPaths,
    report_abs: Path,
    signal_abs: Path,
) -> int:
    """Run pi text mode with supervised diagnostics and attempt-scoped capture."""
    process = spawn_pi_process(command, config, paths)
    if process.stdout is None or process.stderr is None:
        terminate_process_group(process, config.shutdown_timeout, paths.wrapper_log)
        raise PiBashError("failed to capture pi stdout/stderr")

    stderr_lock = Lock()
    activity = OutputActivity(last_output_monotonic=time.monotonic(), lock=Lock())
    with paths.stdout_log.open("w", encoding="utf-8", buffering=1) as stdout_file, paths.stderr_log.open(
        "w",
        encoding="utf-8",
        buffering=1,
    ) as stderr_file:
        emit_wrapper_diagnostic(spawn_notice(process, config, paths), stderr_file, stderr_lock, paths.wrapper_log)
        stdout_thread = Thread(
            target=tee_plain_stream,
            args=(process.stdout, (stdout_file,), activity),
            daemon=True,
        )
        stderr_thread = Thread(
            target=tee_plain_stream,
            args=(process.stderr, (stderr_file,), activity),
            daemon=True,
        )
        threads = (stdout_thread, stderr_thread)
        stdout_thread.start()
        stderr_thread.start()
        try:
            return_code = wait_for_supervised_process(
                process=process,
                config=config,
                paths=paths,
                report_abs=report_abs,
                signal_abs=signal_abs,
                stderr_file=stderr_file,
                stderr_lock=stderr_lock,
                activity=activity,
            )
            ensure_stream_threads_finished(process, threads, config, paths, stderr_file, stderr_lock)
        except Exception:
            if process.poll() is None:
                terminate_process_group(process, config.shutdown_timeout, paths.wrapper_log)
            join_stream_threads(threads, config.shutdown_timeout)
            raise
    append_wrapper_log(paths.wrapper_log, f"completed_at: {utc_timestamp()}\nexit_code: {return_code}\n")
    write_latest_manifest(paths, config, command, "completed", child_pid=process.pid, exit_code=return_code)
    return return_code


def spawn_pi_process(command: Sequence[str], config: LaunchConfig, paths: LaunchPaths) -> subprocess.Popen[str]:
    """Spawn pi in its own process group and record attempt metadata."""
    try:
        process = subprocess.Popen(
            command,
            cwd=config.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
    except OSError as error:
        paths.stdout_log.write_text("")
        paths.stderr_log.write_text(f"failed to execute pi: {error}\n")
        if config.stream:
            paths.events_log.write_text("")
        if paths.raw_events_log.exists():
            paths.raw_events_log.unlink()
        append_wrapper_log(paths.wrapper_log, f"failed_at: {utc_timestamp()}\nerror: failed to execute pi: {error}\n")
        write_latest_manifest(paths, config, command, "spawn_failed", error=str(error))
        raise PiBashError(f"failed to execute pi: {error}") from error

    append_wrapper_log(
        paths.wrapper_log,
        f"spawned_at: {utc_timestamp()}\nchild_pid: {process.pid}\nprocess_group_id: {process.pid}\n",
    )
    write_latest_manifest(paths, config, command, "spawned", child_pid=process.pid)
    return process


def stream_stdout_notice(events_log: Path, raw_events_log: Path | None) -> str:
    """Return the small stdout log notice used in stream mode."""
    notice = f"stream stdout JSON events are captured as lean events in {events_log}\n"
    if raw_events_log is None:
        notice += "raw stream stdout is not persisted; rerun with --raw-events for raw provider events\n"
    else:
        notice += f"raw stream stdout is captured in {raw_events_log}\n"
    return notice


def tee_stdout_stream(
    source: TextIO,
    stdout_file: TextIO,
    events_file: TextIO,
    raw_events_file: TextIO | None,
    stderr_lock: Lock,
    first_output: Event,
    activity: OutputActivity,
    mirror_prefix: str | None,
) -> None:
    """Copy child stdout into lean event logs while avoiding raw JSON duplication."""
    for chunk in source:
        first_output.set()
        activity.mark()
        if raw_events_file is not None:
            raw_events_file.write(chunk)
            raw_events_file.flush()
        lean_event = lean_event_line(chunk)
        if lean_event is None:
            stdout_file.write(chunk)
            stdout_file.flush()
            mirrored = chunk
        else:
            events_file.write(lean_event)
            events_file.flush()
            mirrored = lean_event
        write_mirrored_chunk(mirrored, mirror_prefix, stderr_lock)


def tee_stderr_stream(
    source: TextIO,
    log_files: Sequence[TextIO],
    stderr_lock: Lock,
    first_output: Event,
    activity: OutputActivity,
    mirror_prefix: str | None,
) -> None:
    """Copy child stderr to logs and optionally wrapper stderr."""
    for chunk in source:
        first_output.set()
        activity.mark()
        for log_file in log_files:
            log_file.write(chunk)
            log_file.flush()
        write_mirrored_chunk(chunk, mirror_prefix, stderr_lock)


def write_mirrored_chunk(chunk: str, mirror_prefix: str | None, stderr_lock: Lock) -> None:
    """Write live mirrored child output with an attribution prefix."""
    if mirror_prefix is None:
        return
    with stderr_lock:
        for line in chunk.splitlines(keepends=True):
            sys.stderr.write(f"{mirror_prefix}{line}")
        sys.stderr.flush()


def tee_plain_stream(source: TextIO, log_files: Sequence[TextIO], activity: OutputActivity) -> None:
    """Copy child stream to log files without mirroring raw output to wrapper stderr."""
    for chunk in source:
        activity.mark()
        for log_file in log_files:
            log_file.write(chunk)
            log_file.flush()


def lean_event_line(raw_line: str) -> str | None:
    """Return a sanitized JSONL event or None when stdout is not JSON."""
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    lean_payload = sanitize_event_value(payload, None)
    return json.dumps(lean_payload, sort_keys=True, separators=(",", ":")) + "\n"


def sanitize_event_value(value: object, key: str | None) -> object:
    """Return a compact, non-sensitive representation of a JSON event value."""
    if key is not None and should_redact_event_key(key):
        return redacted_event_summary(value)
    if isinstance(value, dict):
        return {str(child_key): sanitize_event_value(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, list):
        sanitized = [sanitize_event_value(item, None) for item in value[:MAX_EVENT_ARRAY_ITEMS]]
        if len(value) > MAX_EVENT_ARRAY_ITEMS:
            sanitized.append({"redacted": "array_items", "omitted": len(value) - MAX_EVENT_ARRAY_ITEMS})
        return sanitized
    if isinstance(value, str) and len(value) > MAX_EVENT_STRING_CHARS:
        return redacted_event_summary(value)
    return value


def should_redact_event_key(key: str) -> bool:
    """Return whether a JSON event field should be summarized instead of persisted."""
    normalized = key.lower()
    return key in EVENT_REDACT_KEYS or any(fragment in normalized for fragment in EVENT_REDACT_KEY_FRAGMENTS)


def redacted_event_summary(value: object) -> dict[str, object]:
    """Summarize redacted event content without persisting the raw payload."""
    if isinstance(value, str):
        return {"redacted": "string", "chars": len(value), "sha256": hashlib.sha256(value.encode()).hexdigest()}
    if isinstance(value, bytes):
        return {"redacted": "bytes", "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, list):
        return {"redacted": "array", "items": len(value)}
    if isinstance(value, dict):
        return {"redacted": "object", "keys": sorted(str(key) for key in value.keys())}
    if value is None:
        return {"redacted": "null"}
    return {"redacted": type(value).__name__}


def wait_for_supervised_process(
    *,
    process: subprocess.Popen[str],
    config: LaunchConfig,
    paths: LaunchPaths,
    report_abs: Path,
    signal_abs: Path,
    stderr_file: TextIO,
    stderr_lock: Lock,
    activity: OutputActivity,
) -> int:
    """Wait for child exit while emitting bounded wrapper diagnostics."""
    started = time.monotonic()
    next_heartbeat = started + config.heartbeat_interval if config.heartbeat_interval > 0 else float("inf")
    while True:
        return_code = process.poll()
        if return_code is not None:
            return return_code

        elapsed = time.monotonic() - started
        if config.runtime_timeout > 0 and elapsed >= config.runtime_timeout:
            emit_supervision_snapshot(
                "runtime timeout reached; terminating child process group",
                process,
                config,
                paths,
                report_abs,
                signal_abs,
                elapsed,
                activity,
                stderr_file,
                stderr_lock,
            )
            terminate_process_group(process, config.shutdown_timeout, paths.wrapper_log)
            raise PiBashError(f"pi exceeded runtime timeout {config.runtime_timeout:g}s; see wrapper log")

        idle = activity.idle_seconds()
        if config.idle_timeout > 0 and idle >= config.idle_timeout:
            emit_supervision_snapshot(
                "idle timeout reached; terminating child process group",
                process,
                config,
                paths,
                report_abs,
                signal_abs,
                elapsed,
                activity,
                stderr_file,
                stderr_lock,
            )
            terminate_process_group(process, config.shutdown_timeout, paths.wrapper_log)
            raise PiBashError(f"pi produced no child output for {config.idle_timeout:g}s; see wrapper log")

        if time.monotonic() >= next_heartbeat:
            include_snapshot = config.hang_snapshot_after > 0 and elapsed >= config.hang_snapshot_after
            if include_snapshot:
                emit_supervision_snapshot(
                    "child still running",
                    process,
                    config,
                    paths,
                    report_abs,
                    signal_abs,
                    elapsed,
                    activity,
                    stderr_file,
                    stderr_lock,
                )
            else:
                emit_wrapper_diagnostic(
                    f"pi-bash heartbeat: child pid={process.pid} elapsed={elapsed:.1f}s idle={idle:.1f}s\n",
                    stderr_file,
                    stderr_lock,
                    paths.wrapper_log,
                )
            next_heartbeat = time.monotonic() + config.heartbeat_interval
        time.sleep(0.25)


def emit_supervision_snapshot(
    reason: str,
    process: subprocess.Popen[str],
    config: LaunchConfig,
    paths: LaunchPaths,
    report_abs: Path,
    signal_abs: Path,
    elapsed: float,
    activity: OutputActivity,
    stderr_file: TextIO,
    stderr_lock: Lock,
) -> None:
    """Emit sanitized process, artifact, and pi-session state for hung children."""
    lines = [
        f"pi-bash snapshot: {reason}",
        f"attempt_id: {config.attempt_id}",
        f"child_pid: {process.pid}",
        f"elapsed_seconds: {elapsed:.1f}",
        f"idle_seconds: {activity.idle_seconds():.1f}",
        f"stdout_log_bytes: {path_size(paths.stdout_log)}",
        f"stderr_log_bytes: {path_size(paths.stderr_log)}",
        f"events_log_bytes: {path_size(paths.events_log)}",
        f"report: {artifact_state(report_abs)}",
        f"signal: {artifact_state(signal_abs)}",
        format_process_tree(process.pid),
        format_session_diagnostics(config, paths.wrapper_log),
        "",
    ]
    emit_wrapper_diagnostic("\n".join(lines), stderr_file, stderr_lock, paths.wrapper_log)


def ensure_stream_threads_finished(
    process: subprocess.Popen[str],
    threads: Sequence[Thread],
    config: LaunchConfig,
    paths: LaunchPaths,
    stderr_file: TextIO,
    stderr_lock: Lock,
) -> None:
    """Bound stream-reader shutdown and clean descendants if pipes remain open."""
    if join_stream_threads(threads, config.shutdown_timeout):
        return
    emit_wrapper_diagnostic(
        "stream readers did not finish after child exit; terminating process group descendants\n",
        stderr_file,
        stderr_lock,
        paths.wrapper_log,
    )
    signal_process_group(process.pid, SIGTERM, paths.wrapper_log)
    if join_stream_threads(threads, config.shutdown_timeout):
        return
    signal_process_group(process.pid, SIGKILL, paths.wrapper_log)
    if not join_stream_threads(threads, config.shutdown_timeout):
        emit_wrapper_diagnostic(
            "stream readers are still alive after cleanup; continuing to protocol validation\n",
            stderr_file,
            stderr_lock,
            paths.wrapper_log,
        )


def spawn_notice(process: subprocess.Popen[str], config: LaunchConfig, paths: LaunchPaths) -> str:
    """Return a sanitized one-line spawn notice for background Bash visibility."""
    startup_warn = "disabled" if config.startup_warn_after <= 0 else f"{config.startup_warn_after:g}s"
    return (
        f"pi-bash: spawned pid={process.pid} attempt={config.attempt_id} stream={config.stream} "
        f"events={paths.events_log} startup-warn-after={startup_warn}\n"
    )


def path_size(path: Path) -> int:
    """Return file size or zero when absent."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def artifact_state(path: Path) -> str:
    """Return compact artifact existence/size state."""
    if not path.exists():
        return f"missing {path}"
    if not path.is_file():
        return f"not-file {path}"
    return f"present size={path_size(path)} path={path}"


def emit_startup_warning_if_silent(
    *,
    process: subprocess.Popen[str],
    first_output: Event,
    startup_warn_after: float,
    stderr_file: TextIO,
    stderr_lock: Lock,
    wrapper_log: Path,
) -> None:
    """Warn when a stream worker has not emitted its first line yet."""
    if startup_warn_after <= 0 or first_output.is_set():
        return

    deadline = time.monotonic() + startup_warn_after
    while process.poll() is None and not first_output.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process_tree = format_process_tree(process.pid)
            message = (
                f"no child stdout/stderr after {startup_warn_after:g}s in stream mode; "
                f"continuing without terminating process group {process.pid}\n{process_tree}\n"
            )
            emit_wrapper_diagnostic(message, stderr_file, stderr_lock, wrapper_log)
            return
        first_output.wait(min(0.25, remaining))


def join_stream_threads(threads: Sequence[Thread], timeout: float) -> bool:
    """Join stream reader threads within a total timeout."""
    deadline = time.monotonic() + max(timeout, 0.0)
    for thread in threads:
        remaining = max(0.0, deadline - time.monotonic())
        thread.join(timeout=remaining)
    return not any(thread.is_alive() for thread in threads)


def terminate_process_group(process: subprocess.Popen[str], timeout: float, wrapper_log: Path) -> None:
    """Terminate the child process group, escalating to SIGKILL if needed."""
    signal_process_group(process.pid, SIGTERM, wrapper_log)
    try:
        process.wait(timeout=max(timeout, 0.1))
    except subprocess.TimeoutExpired:
        signal_process_group(process.pid, SIGKILL, wrapper_log)
        try:
            process.wait(timeout=max(timeout, 0.1))
        except subprocess.TimeoutExpired as error:
            append_wrapper_log(wrapper_log, f"failed_at: {utc_timestamp()}\nerror: process group did not exit\n")
            raise PiBashError("process group did not exit after SIGKILL") from error


def signal_process_group(process_group_id: int, termination_signal: int, wrapper_log: Path) -> None:
    """Send a signal to a process group and record non-fatal signaling failures."""
    try:
        os.killpg(process_group_id, termination_signal)
    except ProcessLookupError:
        append_wrapper_log(
            wrapper_log,
            f"signal_at: {utc_timestamp()}\nsignal: {termination_signal}\nprocess_group_missing: {process_group_id}\n",
        )
    except PermissionError as error:
        append_wrapper_log(
            wrapper_log,
            f"signal_at: {utc_timestamp()}\nsignal: {termination_signal}\nerror: {error}\n",
        )


def write_launch_metadata(
    *,
    wrapper_log: Path,
    config: LaunchConfig,
    command: Sequence[str],
    prompt: str,
    skill_count: int,
    paths: LaunchPaths,
) -> None:
    """Write wrapper-side launch diagnostics before child output exists."""
    wrapper_log.parent.mkdir(parents=True, exist_ok=True)
    metadata = [
        f"started_at: {utc_timestamp()}",
        f"agent_id: {config.agent_id}",
        f"attempt_id: {config.attempt_id}",
        f"stream: {config.stream}",
        f"raw_events: {config.raw_events}",
        f"allow_extensions: {config.allow_extensions}",
        f"extension_count: {len(config.extensions)}",
        f"tools: {config.tools or ''}",
        f"model: {config.model}",
        f"thinking: {config.thinking or ''}",
        f"startup_warn_after_seconds: {config.startup_warn_after:g}",
        f"shutdown_timeout_seconds: {config.shutdown_timeout:g}",
        f"mirror_prefix: {config.mirror_prefix or ''}",
        f"heartbeat_interval_seconds: {config.heartbeat_interval:g}",
        f"hang_snapshot_after_seconds: {config.hang_snapshot_after:g}",
        f"runtime_timeout_seconds: {config.runtime_timeout:g}",
        f"idle_timeout_seconds: {config.idle_timeout:g}",
        f"prompt_bytes: {len(prompt.encode('utf-8'))}",
        f"skill_count: {skill_count}",
        f"stdout_log: {paths.stdout_log}",
        f"stderr_log: {paths.stderr_log}",
        f"events_log: {paths.events_log}",
        f"raw_events_log: {paths.raw_events_log if config.raw_events else ''}",
        f"latest_manifest: {paths.latest_manifest}",
        f"command: {render_command_preview(command)}",
        "",
    ]
    wrapper_log.write_text("\n".join(metadata), encoding="utf-8")


def write_latest_manifest(
    paths: LaunchPaths,
    config: LaunchConfig,
    command: Sequence[str],
    status: str,
    *,
    child_pid: int | None = None,
    exit_code: int | None = None,
    error: str | None = None,
) -> None:
    """Write the latest-attempt manifest without exposing prompt text."""
    payload: dict[str, object] = {
        "agent_id": config.agent_id,
        "attempt_id": config.attempt_id,
        "updated_at": utc_timestamp(),
        "status": status,
        "cwd": str(config.cwd),
        "stream": config.stream,
        "model": config.model,
        "thinking": config.thinking,
        "command": render_command_preview(command),
        "stdout_log": str(paths.stdout_log),
        "stderr_log": str(paths.stderr_log),
        "events_log": str(paths.events_log),
        "raw_events_log": str(paths.raw_events_log) if config.raw_events else "",
        "wrapper_log": str(paths.wrapper_log),
    }
    if child_pid is not None:
        payload["child_pid"] = child_pid
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if error is not None:
        payload["error"] = error
    paths.latest_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.latest_manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_wrapper_log(wrapper_log: Path, message: str) -> None:
    """Append wrapper-side diagnostics without touching protocol stdout."""
    wrapper_log.parent.mkdir(parents=True, exist_ok=True)
    with wrapper_log.open("a", encoding="utf-8") as log_file:
        log_file.write(message if message.endswith("\n") else f"{message}\n")


def emit_wrapper_diagnostic(message: str, stderr_file: TextIO, stderr_lock: Lock, wrapper_log: Path) -> None:
    """Write a wrapper diagnostic to stderr log, wrapper log, and live stderr."""
    rendered = message if message.endswith("\n") else f"{message}\n"
    append_wrapper_log(wrapper_log, rendered)
    stderr_file.write(rendered)
    stderr_file.flush()
    with stderr_lock:
        sys.stderr.write(rendered)
        sys.stderr.flush()


def render_command_preview(command: Sequence[str]) -> str:
    """Render argv with prompt-like and secret values redacted."""
    redacted: list[str] = []
    redact_next = False
    for value in command:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        flag, separator, _secret = value.partition("=")
        if separator and flag in SENSITIVE_PROCESS_ARG_FLAGS:
            redacted.append(f"{flag}=<redacted>")
            continue
        redacted.append(value)
        if value in SENSITIVE_PROCESS_ARG_FLAGS:
            redact_next = True
    return shlex.join(redacted)


def collect_process_tree(root_pid: int) -> list[ProcessSnapshot]:
    """Collect a best-effort process tree rooted at a child PID."""
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,stat=,etime=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    processes: dict[int, ProcessSnapshot] = {}
    children_by_parent: dict[int, list[int]] = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 4)
        if len(parts) != 5:
            continue
        pid_text, ppid_text, stat, etime, command = parts
        try:
            pid = int(pid_text)
            ppid = int(ppid_text)
        except ValueError:
            continue
        processes[pid] = ProcessSnapshot(
            pid=pid,
            ppid=ppid,
            stat=stat,
            etime=etime,
            command=sanitize_process_command(command),
        )
        children_by_parent.setdefault(ppid, []).append(pid)

    tree: list[ProcessSnapshot] = []
    stack = [root_pid]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        snapshot = processes.get(pid)
        if snapshot is not None:
            tree.append(snapshot)
        stack.extend(reversed(children_by_parent.get(pid, [])))
    return tree


def format_process_tree(root_pid: int) -> str:
    """Format a sanitized process tree for diagnostics."""
    snapshots = collect_process_tree(root_pid)
    if not snapshots:
        return f"process_tree: unavailable for pid {root_pid}"
    lines = ["process_tree:"]
    for snapshot in snapshots:
        command = truncate_text(snapshot.command, 500)
        lines.append(
            f"- pid={snapshot.pid} ppid={snapshot.ppid} stat={snapshot.stat} etime={snapshot.etime} command={command}"
        )
    return "\n".join(lines)


def sanitize_process_command(command: str) -> str:
    """Redact prompt-like and secret arguments from a process command string."""
    if any(flag in command for flag in SENSITIVE_PROCESS_ARG_PREFIXES):
        return redact_unparsed_command(command)
    try:
        parts = shlex.split(command)
    except ValueError:
        return redact_unparsed_command(command)
    return render_command_preview(parts)


def redact_unparsed_command(command: str) -> str:
    """Best-effort redaction when process command parsing fails or argv boundaries are unavailable."""
    matches = [(index, flag) for flag in SENSITIVE_PROCESS_ARG_PREFIXES if (index := command.find(flag)) >= 0]
    if not matches:
        return command
    first_index, first_flag = min(matches, key=lambda item: item[0])
    return f"{command[:first_index]}{first_flag} <redacted>"


def truncate_text(value: str, limit: int) -> str:
    """Truncate long diagnostics while preserving deterministic output."""
    if len(value) <= limit:
        return value
    return f"{value[: limit - 13]}...<truncated>"


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp for wrapper diagnostics."""
    return dt.datetime.now(dt.UTC).isoformat()


def build_attempt_id() -> str:
    """Return a filesystem-safe attempt id for preserving retry evidence."""
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-p{os.getpid()}"


def format_session_diagnostics(config: LaunchConfig, marker_path: Path) -> str:
    """Summarize newest pi session state for this attempt's cwd, if available."""
    session_dir = pi_session_dir(config.cwd)
    if not session_dir.exists():
        return f"pi_session: none session_dir={session_dir}"
    try:
        cutoff = marker_path.stat().st_mtime - 5.0
    except OSError:
        cutoff = time.time() - 5.0
    candidates = sorted(
        (path for path in session_dir.glob("*.jsonl") if path.is_file() and path.stat().st_mtime >= cutoff),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return f"pi_session: none_since_attempt session_dir={session_dir}"
    newest = candidates[0]
    return summarize_session_file(newest)


def pi_session_dir(cwd: Path) -> Path:
    """Return pi's cwd-scoped session directory path."""
    agent_dir = Path(os.environ.get("PI_CODING_AGENT_DIR", "~/.pi/agent")).expanduser()
    encoded = "--" + str(cwd).strip("/").replace("/", "-") + "--"
    return agent_dir / "sessions" / encoded


def summarize_session_file(path: Path) -> str:
    """Return a compact sanitized summary of a pi JSONL session tail."""
    last_event: dict[str, object] | None = None
    last_tool_call: dict[str, object] | None = None
    for line in tail_file_lines(path, MAX_SESSION_TAIL_BYTES, MAX_SESSION_TAIL_LINES):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            last_event = event
            tool_call = find_tool_call(event)
            if tool_call is not None:
                last_tool_call = tool_call
    if last_event is None:
        return f"pi_session: {path} last_event=unreadable"
    parts = [f"pi_session: {path}", f"last_event: {summarize_session_event(last_event)}"]
    if last_tool_call is not None:
        parts.append(f"last_tool_call: {summarize_tool_call(last_tool_call)}")
    return "\n".join(parts)


def tail_file_lines(path: Path, max_bytes: int, max_lines: int) -> list[str]:
    """Read a bounded tail of a text file."""
    try:
        size = path.stat().st_size
        with path.open("rb") as file:
            if size > max_bytes:
                file.seek(-max_bytes, os.SEEK_END)
                file.readline()
            data = file.read()
    except OSError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()[-max_lines:]


def find_tool_call(event: dict[str, object]) -> dict[str, object] | None:
    """Find the last tool call object inside a pi session event."""
    message = event.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    for item in reversed(content):
        if isinstance(item, dict) and item.get("type") == "toolCall":
            return item
    return None


def summarize_session_event(event: dict[str, object]) -> str:
    """Summarize a pi session event without raw message content."""
    event_type = str(event.get("type", "unknown"))
    timestamp = str(event.get("timestamp", ""))
    message = event.get("message")
    if isinstance(message, dict):
        role = str(message.get("role", ""))
        stop_reason = str(message.get("stopReason", ""))
        return f"type={event_type} role={role} stopReason={stop_reason} timestamp={timestamp}"
    return f"type={event_type} timestamp={timestamp}"


def summarize_tool_call(tool_call: dict[str, object]) -> str:
    """Summarize a tool call with sensitive values redacted."""
    name = str(tool_call.get("name", "unknown"))
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        keys = sorted(str(key) for key in arguments.keys())
        timeout = arguments.get("timeout", "<none>")
        command = arguments.get("command")
        command_summary = ""
        if isinstance(command, str):
            command_summary = f" command_sha256={hashlib.sha256(command.encode()).hexdigest()}"
            command_summary += f" command_preview={shlex.quote(truncate_text(command, 160))}"
        return f"name={name} keys={keys} timeout={timeout}{command_summary}"
    return f"name={name} arguments={redacted_event_summary(arguments)}"


def build_worker_prompt(config: LaunchConfig, skills: Sequence[ResolvedSkill]) -> str:
    """Synthesize the programmatic pi worker prompt from wrapper arguments."""
    mux_root = Path(__file__).resolve().parent.parent
    signal_command = " ".join(
        [
            "uv",
            "run",
            shlex.quote(str(mux_root / "tools" / "signal.py")),
            shlex.quote(config.signal_path),
            "--path",
            shlex.quote(config.report_path),
            "--status",
            "success",
        ]
    )

    lines = [
        "# pi-bash worker protocol",
        "",
        "You are running as a programmatic pi worker supervised by pi-bash.py.",
        "All substantive output must be written to the declared report file, not to chat/stdout.",
        "After successful report and signal creation, your final textual response must be exactly `0`.",
        "Do not launch nested subagents.",
        "Do not use control-plane bridge tools or `report_parent`.",
        "",
        "## Bash safety for programmatic workers",
        "- Never run long-lived servers, watchers, or interactive commands in the foreground.",
        "- Every Bash command that can hang must include an explicit timeout or a background PID cleanup recipe.",
        "- For dev servers: start in the background, write logs to a declared file, wait with a bounded readiness loop, run checks, then kill the PID.",
        "- If a required command has no safe bounded form, document the deferral in the report instead of hanging.",
        "",
        "## Declared dispatch",
        f"- Role: {config.role}",
    ]
    if config.worker_type:
        lines.append(f"- Worker type: {config.worker_type}")
    lines.extend(
        [
            f"- Objective: {config.objective}",
            f"- Scope: {config.scope}",
            f"- Report path: `{config.report_path}`",
            f"- Signal path: `{config.signal_path}`",
            "",
            "## Task",
            config.task,
            "",
            "## Required report format",
            f"Write the report to `{config.report_path}` with these headings:",
        ]
    )
    lines.extend(f"- `{heading}`" for heading in REQUIRED_REPORT_HEADINGS)
    lines.extend(
        [
            "",
            "The `## Executive Summary` section must include a concise status and evidence summary.",
            "The `### Next Steps` subsection must state the recommended next action and any relevant file paths.",
            "",
            "## Required success signal",
            "After writing the report, create the success signal with this exact command:",
            "",
            "```bash",
            signal_command,
            "```",
            "",
        ]
    )
    lines.extend(build_skill_prompt_block(skills))
    lines.extend(
        [
            "## Completion contract",
            "Return exactly `0` after the report and success signal are written.",
            "If you cannot complete the task, write a failure report if possible, do not create a success signal, and return non-zero text.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_skill_prompt_block(skills: Sequence[ResolvedSkill]) -> list[str]:
    """Build prompt lines describing preloaded skills."""
    if not skills:
        return [
            "## Preloaded skills",
            "No additional skills were requested for preload.",
            "",
        ]

    lines = [
        "## Preloaded skills",
        "The wrapper passed these skills to pi with `--skill` in the order shown below.",
        "Apply them before substantive work. The file-protocol instructions in this prompt remain mandatory.",
    ]
    for index, skill in enumerate(skills, start=1):
        lines.extend(
            [
                f"{index}. Requested: `{skill.requested}`",
                f"   Resolved path: `{skill.cli_path}`",
                f"   Content source: `{skill.content_path}`",
                f"   Content SHA-256: `{skill.content_sha256}`",
            ]
        )
    lines.append("")
    return lines


def resolve_skill(cwd: Path, requested: str) -> ResolvedSkill:
    """Resolve a skill name or path and verify readable content."""
    if not requested.strip():
        raise PiBashError("skill arguments must not be empty")

    path_candidate = expand_path_text(requested, cwd)
    if is_path_like(requested):
        if not path_candidate.exists():
            raise PiBashError(f"skill path does not exist: {requested}")
        return build_resolved_skill(requested, path_candidate)

    matches = find_named_skill_candidates(cwd, requested)
    unique_matches = dedupe_paths(matches)
    if not unique_matches:
        raise PiBashError(f"could not resolve skill by name: {requested}")
    if len(unique_matches) > 1:
        rendered_matches = ", ".join(str(path) for path in unique_matches)
        raise PiBashError(f"ambiguous skill name {requested!r}: {rendered_matches}")
    return build_resolved_skill(requested, unique_matches[0])


def is_path_like(value: str) -> bool:
    """Return whether a skill argument should be treated as a path."""
    return (
        "/" in value
        or "\\" in value
        or value.startswith(".")
        or value.startswith("~")
        or "$" in value
        or value.endswith(".md")
    )


def expand_path_text(value: str, cwd: Path) -> Path:
    """Expand environment variables and resolve a possibly relative path."""
    expanded = Path(os.path.expandvars(value)).expanduser()
    if not expanded.is_absolute():
        expanded = cwd / expanded
    return expanded.resolve(strict=False)


def find_named_skill_candidates(cwd: Path, name: str) -> list[Path]:
    """Find deterministic candidate paths for a named skill."""
    candidates: list[Path] = []
    candidates.extend(
        [
            cwd / ".claude" / "commands" / f"{name}.md",
            cwd / ".claude" / "commands" / name / "SKILL.md",
            cwd / ".claude" / "skills" / name / "SKILL.md",
            cwd / ".claude" / "skills" / f"{name}.md",
        ]
    )

    plugins_dir = cwd / "plugins"
    if plugins_dir.exists():
        for plugin_dir in sorted(path for path in plugins_dir.iterdir() if path.is_dir()):
            candidates.extend(
                [
                    plugin_dir / "skills" / name / "SKILL.md",
                    plugin_dir / "skills" / f"{name}.md",
                ]
            )

    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        root = Path(os.path.expandvars(plugin_root)).expanduser().resolve(strict=False)
        candidates.extend([root / "skills" / name / "SKILL.md", root / "skills" / f"{name}.md"])

    pi_agent_dir = Path(os.environ.get("PI_CODING_AGENT_DIR", "~/.pi/agent")).expanduser()
    candidates.extend([pi_agent_dir / "skills" / name / "SKILL.md", pi_agent_dir / "skills" / f"{name}.md"])
    return [candidate.resolve(strict=False) for candidate in candidates if candidate.exists()]


def dedupe_paths(paths: Sequence[Path]) -> list[Path]:
    """Dedupe paths while preserving order."""
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def build_resolved_skill(requested: str, path: Path) -> ResolvedSkill:
    """Create resolved skill metadata after readability checks."""
    if path.is_dir():
        content_path = skill_directory_content_path(path)
        cli_path = path
    elif path.is_file():
        content_path = path
        cli_path = path
    else:
        raise PiBashError(f"skill path is neither a file nor directory: {path}")

    try:
        content = content_path.read_bytes()
    except OSError as error:
        raise PiBashError(f"skill content is not readable: {content_path}: {error}") from error

    return ResolvedSkill(
        requested=requested,
        cli_path=cli_path,
        content_path=content_path,
        content_sha256=hashlib.sha256(content).hexdigest(),
    )


def skill_directory_content_path(path: Path) -> Path:
    """Choose the deterministic readable content file for a skill directory."""
    skill_md = path / "SKILL.md"
    if skill_md.exists():
        return skill_md
    markdown_files = sorted(child for child in path.iterdir() if child.is_file() and child.suffix == ".md")
    if not markdown_files:
        raise PiBashError(f"skill directory has no readable markdown entrypoint: {path}")
    return markdown_files[0]


def log_paths(cwd: Path, session_dir: str, agent_id: str, attempt_id: str) -> LaunchPaths:
    """Return attempt-scoped log paths for the worker."""
    session_abs = resolve_project_path(cwd, session_dir)
    safe_name = safe_log_name(agent_id)
    safe_attempt = safe_log_name(attempt_id)
    logs_dir = session_abs / "logs"
    prefix = f"{safe_name}.{safe_attempt}"
    return LaunchPaths(
        stdout_log=logs_dir / f"{prefix}.stdout.log",
        stderr_log=logs_dir / f"{prefix}.stderr.log",
        events_log=logs_dir / f"{prefix}.events.jsonl",
        raw_events_log=logs_dir / f"{prefix}.raw-events.jsonl",
        wrapper_log=logs_dir / f"{prefix}.wrapper.log",
        latest_manifest=logs_dir / f"{safe_name}.latest.json",
    )


def safe_log_name(agent_id: str) -> str:
    """Create a safe log filename from an opaque agent id."""
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", agent_id).strip("._")
    return safe_name or "worker"


def resolve_project_path(cwd: Path, value: str) -> Path:
    """Resolve a project path relative to cwd unless already absolute."""
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        path = cwd / path
    return path.resolve(strict=False)


def clear_previous_artifacts(*, report_abs: Path, signal_abs: Path) -> None:
    """Remove prior protocol artifacts so success must come from this launch."""
    clear_previous_artifact(report_abs, "report")
    clear_previous_artifact(signal_abs, "signal")


def clear_previous_artifact(path: Path, artifact_name: str) -> None:
    """Remove one prior protocol artifact if it is a regular file."""
    if not path.exists():
        return
    if not path.is_file():
        raise PiBashError(f"declared {artifact_name} path exists and is not a file: {path}")
    path.unlink()


def record_protocol_success_diagnostic(
    *,
    stderr_log: Path,
    wrapper_log: Path,
    result: int | None,
    lifecycle_error: PiBashError | None,
) -> None:
    """Record non-fatal child issues when protocol validation succeeded."""
    details: list[str] = []
    if result is not None and result != 0:
        details.append(f"child_exit_code={result}")
    if lifecycle_error is not None:
        details.append(f"lifecycle_error={lifecycle_error}")
    message = f"pi-bash: protocol valid; treating child issue as success ({'; '.join(details)})\n"
    append_wrapper_log(wrapper_log, message)
    stderr_log.parent.mkdir(parents=True, exist_ok=True)
    with stderr_log.open("a", encoding="utf-8") as log_file:
        log_file.write(message)


def validate_protocol_outputs(
    *,
    report_abs: Path,
    signal_abs: Path,
    report_path_arg: str,
    cwd: Path,
) -> None:
    """Validate report and signal artifacts after pi exits."""
    if not report_abs.exists() or not report_abs.is_file():
        raise PiBashError(f"missing report file: {report_abs}")
    if not signal_abs.exists() or not signal_abs.is_file():
        raise PiBashError(f"missing signal file: {signal_abs}")

    signal_values = parse_signal_file(signal_abs)
    if signal_values.get("status") != "success":
        raise PiBashError(f"signal status is not success: {signal_abs}")
    signal_report_path = signal_values.get("path")
    if signal_report_path is None:
        raise PiBashError(f"signal missing path field: {signal_abs}")
    if resolve_project_path(cwd, signal_report_path) != resolve_project_path(cwd, report_path_arg):
        raise PiBashError(
            f"signal path does not match declared report path: {signal_report_path} != {report_path_arg}"
        )

    report_text = report_abs.read_text(errors="replace")
    missing_headings = [heading for heading in REQUIRED_REPORT_HEADINGS if heading not in report_text]
    if missing_headings:
        raise PiBashError(f"report missing required headings: {', '.join(missing_headings)}")


def parse_signal_file(path: Path) -> dict[str, str]:
    """Parse the simple key-value mux signal format."""
    values: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


if __name__ == "__main__":
    sys.exit(main())
