#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run a Claude Code print-mode worker behind a file-based contract."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Sequence, TextIO

DEFAULT_STARTUP_TIMEOUT_SECONDS = 60.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 5.0
# Do not import stdlib signal here: this directory also contains signal.py.
SIGTERM = 15
SIGKILL = 9
SENSITIVE_PROCESS_ARG_FLAGS = frozenset(
    {
        "-p",
        "--append-system-prompt",
        "--api-key",
        "--mcp-config",
        "--settings",
        "--system-prompt",
    }
)
SENSITIVE_PROCESS_ARG_PREFIXES = tuple(sorted(SENSITIVE_PROCESS_ARG_FLAGS, key=len, reverse=True))
MULTI_VALUE_SENSITIVE_PROCESS_ARG_FLAGS = frozenset({"--mcp-config"})
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
MAX_APPEND_SYSTEM_PROMPT_CHARS = 120_000
CLAUDE_CODE_NPX_PACKAGE = "@anthropic-ai/claude-code"


class CCBashError(RuntimeError):
    """Raised when the cc-bash wrapper cannot complete safely."""


@dataclass(frozen=True)
class ResolvedSkill:
    """Resolved skill preload metadata."""

    requested: str
    cli_path: Path
    content_path: Path
    content_sha256: str
    content_text: str


@dataclass(frozen=True)
class ProcessSnapshot:
    """Sanitized process metadata for startup diagnostics."""

    pid: int
    ppid: int
    stat: str
    etime: str
    command: str


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
    permission_mode: str | None
    output_format: str
    stream: bool
    raw_events: bool
    startup_timeout: float
    shutdown_timeout: float
    allowed_tools: tuple[str, ...]
    disallowed_tools: tuple[str, ...]
    add_dirs: tuple[str, ...]
    mcp_configs: tuple[str, ...]
    strict_mcp_config: bool
    settings: str | None
    setting_sources: str | None
    plugin_dirs: tuple[str, ...]
    append_system_prompts: tuple[str, ...]
    no_session_persistence: bool
    bare: bool
    skills: tuple[str, ...]
    cwd: Path
    claude_bin: str | None
    npx_bin: str | None


def main(argv: Sequence[str] | None = None) -> int:
    """Run the cc-bash CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "launch":
            return launch_from_args(args)
        raise CCBashError(f"unsupported command: {args.command}")
    except CCBashError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    launch_parser = subparsers.add_parser("launch", help="launch a supervised Claude Code worker")
    launch_parser.add_argument("session_dir", help="Project-root-relative or absolute mux/session directory")
    launch_parser.add_argument("agent_id", help="Opaque worker identifier used for log filenames")
    launch_parser.add_argument("--role", required=True, help="Project-defined opaque role label")
    launch_parser.add_argument("--worker-type", default=None, help="Optional orchestration worker type")
    launch_parser.add_argument("--objective", required=True, help="Declared worker objective")
    launch_parser.add_argument("--scope", required=True, help="Declared worker scope")
    launch_parser.add_argument("--task", required=True, help="Bounded worker task instructions")
    launch_parser.add_argument("--report-path", required=True, help="Required worker report path")
    launch_parser.add_argument("--signal-path", required=True, help="Required success signal path")
    launch_parser.add_argument("--model", required=True, help="Claude Code model argument to pass through")
    launch_parser.add_argument("--permission-mode", default=None, help="Claude Code permission mode")
    launch_parser.add_argument(
        "--output-format",
        default="text",
        choices=["text", "json", "stream-json"],
        help="Claude Code print-mode output format",
    )
    launch_parser.add_argument(
        "--allowed-tool",
        action="append",
        default=[],
        help="Claude Code allowed tool entry; repeat to preserve order",
    )
    launch_parser.add_argument(
        "--disallowed-tool",
        action="append",
        default=[],
        help="Claude Code disallowed tool entry; repeat to preserve order",
    )
    launch_parser.add_argument(
        "--add-dir",
        action="append",
        default=[],
        help="Directory to allow Claude Code to access; repeat to preserve order",
    )
    launch_parser.add_argument(
        "--mcp-config",
        action="append",
        default=[],
        help="MCP config file or JSON string; repeat to preserve order",
    )
    launch_parser.add_argument("--strict-mcp-config", action="store_true", help="Use only provided MCP configs")
    launch_parser.add_argument("--settings", default=None, help="Claude Code settings file or JSON")
    launch_parser.add_argument("--setting-sources", default=None, help="Claude Code setting sources")
    launch_parser.add_argument(
        "--plugin-dir",
        action="append",
        default=[],
        help="Claude Code plugin directory; repeat to preserve order",
    )
    launch_parser.add_argument(
        "--append-system-prompt",
        action="append",
        default=[],
        help="Additional append-only Claude Code system prompt text; repeat to preserve order",
    )
    launch_parser.add_argument(
        "--persist-session",
        action="store_true",
        help="Do not pass --no-session-persistence to Claude Code print mode",
    )
    launch_parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream raw Claude Code JSON events to stderr and an events log; overrides --output-format",
    )
    launch_parser.add_argument(
        "--raw-events",
        action="store_true",
        help="In stream mode, additionally persist unsanitized child stdout to logs/<agent-id>.raw-events.jsonl",
    )
    launch_parser.add_argument(
        "--startup-timeout",
        type=parse_non_negative_float,
        default=DEFAULT_STARTUP_TIMEOUT_SECONDS,
        help=(
            "Seconds to wait in stream mode for the first child stdout/stderr line before terminating; "
            "use 0 to disable"
        ),
    )
    launch_parser.add_argument(
        "--shutdown-timeout",
        type=parse_non_negative_float,
        default=DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
        help="Seconds to wait for stream reader threads to drain after child exit before cleaning up descendants",
    )
    launch_parser.add_argument("--bare", action="store_true", help="Pass Claude Code --bare")
    launch_parser.add_argument(
        "--skill",
        action="append",
        default=[],
        help="Skill name or path to preload through appended system prompt context",
    )
    launch_parser.add_argument("--cwd", default=".", help="Project root / worker current directory")
    launch_parser.add_argument("--claude-bin", default=None, help="Force a Claude Code executable path")
    launch_parser.add_argument("--npx-bin", default=None, help="Force an npx executable path for fallback")
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
    """Validate arguments, launch Claude Code, and validate the file protocol."""
    config = parse_launch_config(args)
    resolved_skills = tuple(resolve_skill(config.cwd, skill) for skill in config.skills)
    prompt = build_worker_prompt(config, resolved_skills)
    append_system_prompt = build_append_system_prompt(resolved_skills, config.append_system_prompts)
    stdout_log, stderr_log, events_log, raw_events_log, wrapper_log = log_paths(
        config.cwd,
        config.session_dir,
        config.agent_id,
    )
    report_abs = resolve_project_path(config.cwd, config.report_path)
    signal_abs = resolve_project_path(config.cwd, config.signal_path)
    clear_previous_signal(signal_abs)

    result = run_claude(
        config,
        append_system_prompt,
        prompt,
        stdout_log,
        stderr_log,
        events_log,
        raw_events_log,
        wrapper_log,
    )
    if result != 0:
        raise CCBashError(f"Claude Code exited with code {result}; see {stdout_log} and {stderr_log}")

    validate_protocol_outputs(
        report_abs=report_abs,
        signal_abs=signal_abs,
        report_path_arg=config.report_path,
        cwd=config.cwd,
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
        raise CCBashError(f"cwd does not exist or is not a directory: {cwd}")

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
            raise CCBashError(f"{name} is required")

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
        permission_mode=str(args.permission_mode) if args.permission_mode else None,
        output_format="stream-json" if args.stream else str(args.output_format),
        stream=bool(args.stream),
        raw_events=bool(args.raw_events),
        startup_timeout=float(args.startup_timeout),
        shutdown_timeout=float(args.shutdown_timeout),
        allowed_tools=tuple(str(tool) for tool in args.allowed_tool),
        disallowed_tools=tuple(str(tool) for tool in args.disallowed_tool),
        add_dirs=tuple(str(directory) for directory in args.add_dir),
        mcp_configs=tuple(str(config) for config in args.mcp_config),
        strict_mcp_config=bool(args.strict_mcp_config),
        settings=str(args.settings) if args.settings else None,
        setting_sources=str(args.setting_sources) if args.setting_sources else None,
        plugin_dirs=tuple(str(directory) for directory in args.plugin_dir),
        append_system_prompts=tuple(str(prompt) for prompt in args.append_system_prompt),
        no_session_persistence=not bool(args.persist_session),
        bare=bool(args.bare),
        skills=tuple(str(skill) for skill in args.skill),
        cwd=cwd,
        claude_bin=str(args.claude_bin) if args.claude_bin else None,
        npx_bin=str(args.npx_bin) if args.npx_bin else None,
    )


def run_claude(
    config: LaunchConfig,
    append_system_prompt: str | None,
    prompt: str,
    stdout_log: Path,
    stderr_log: Path,
    events_log: Path,
    raw_events_log: Path,
    wrapper_log: Path,
) -> int:
    """Run the underlying Claude Code process and persist raw output to log files."""
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stderr_log.parent.mkdir(parents=True, exist_ok=True)
    events_log.parent.mkdir(parents=True, exist_ok=True)

    command = build_claude_command(config, append_system_prompt, prompt)
    write_launch_metadata(
        wrapper_log=wrapper_log,
        config=config,
        command=command,
        prompt=prompt,
        append_system_prompt=append_system_prompt,
        skill_count=len(config.skills),
        stdout_log=stdout_log,
        stderr_log=stderr_log,
        events_log=events_log,
        raw_events_log=raw_events_log,
    )
    if not config.stream and raw_events_log.exists():
        raw_events_log.unlink()
    if config.stream:
        return run_streaming_claude(
            command,
            config.cwd,
            stdout_log,
            stderr_log,
            events_log,
            raw_events_log,
            wrapper_log,
            config.raw_events,
            config.startup_timeout,
            config.shutdown_timeout,
        )

    try:
        result = subprocess.run(
            command,
            cwd=config.cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        stdout_log.write_text("")
        stderr_log.write_text(f"failed to execute Claude Code: {error}\n")
        append_wrapper_log(wrapper_log, f"failed_at: {utc_timestamp()}\nerror: failed to execute Claude Code: {error}\n")
        raise CCBashError(f"failed to execute Claude Code: {error}") from error

    stdout_log.write_text(result.stdout)
    stderr_log.write_text(result.stderr)
    append_wrapper_log(wrapper_log, f"completed_at: {utc_timestamp()}\nexit_code: {result.returncode}\n")
    return result.returncode


def run_streaming_claude(
    command: Sequence[str],
    cwd: Path,
    stdout_log: Path,
    stderr_log: Path,
    events_log: Path,
    raw_events_log: Path,
    wrapper_log: Path,
    raw_events: bool,
    startup_timeout: float,
    shutdown_timeout: float,
) -> int:
    """Run Claude Code while teeing child streams to logs and wrapper stderr."""
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
    except OSError as error:
        stdout_log.write_text("")
        stderr_log.write_text(f"failed to execute Claude Code: {error}\n")
        events_log.write_text("")
        if raw_events_log.exists():
            raw_events_log.unlink()
        append_wrapper_log(wrapper_log, f"failed_at: {utc_timestamp()}\nerror: failed to execute Claude Code: {error}\n")
        raise CCBashError(f"failed to execute Claude Code: {error}") from error

    append_wrapper_log(
        wrapper_log,
        f"spawned_at: {utc_timestamp()}\nchild_pid: {process.pid}\nprocess_group_id: {process.pid}\n",
    )

    if process.stdout is None or process.stderr is None:
        terminate_process_group(process, shutdown_timeout, wrapper_log)
        raise CCBashError("failed to capture Claude Code stdout/stderr")

    stderr_lock = Lock()
    first_output = Event()
    if not raw_events and raw_events_log.exists():
        raw_events_log.unlink()
    raw_events_file: TextIO | None = None
    with stdout_log.open("w", encoding="utf-8", buffering=1) as stdout_file, stderr_log.open(
        "w",
        encoding="utf-8",
        buffering=1,
    ) as stderr_file, events_log.open("w", encoding="utf-8", buffering=1) as events_file:
        stdout_file.write(stream_stdout_notice(events_log, raw_events_log if raw_events else None))
        stdout_file.flush()
        if raw_events:
            raw_events_file = raw_events_log.open("w", encoding="utf-8", buffering=1)
        try:
            stdout_thread = Thread(
                target=tee_stdout_stream,
                args=(process.stdout, stdout_file, events_file, raw_events_file, stderr_lock, first_output),
                daemon=True,
            )
            stderr_thread = Thread(
                target=tee_stderr_stream,
                args=(process.stderr, (stderr_file,), stderr_lock, first_output),
                daemon=True,
            )
            threads = (stdout_thread, stderr_thread)
            stdout_thread.start()
            stderr_thread.start()
            try:
                enforce_startup_timeout(
                    process=process,
                    first_output=first_output,
                    startup_timeout=startup_timeout,
                    stderr_file=stderr_file,
                    stderr_lock=stderr_lock,
                    wrapper_log=wrapper_log,
                    shutdown_timeout=shutdown_timeout,
                )
                return_code = process.wait()
                if not join_stream_threads(threads, shutdown_timeout):
                    emit_wrapper_diagnostic(
                        "stream readers did not finish after child exit; terminating process group descendants\n",
                        stderr_file,
                        stderr_lock,
                        wrapper_log,
                    )
                    signal_process_group(process.pid, SIGTERM, wrapper_log)
                    if not join_stream_threads(threads, shutdown_timeout):
                        signal_process_group(process.pid, SIGKILL, wrapper_log)
                        if not join_stream_threads(threads, shutdown_timeout):
                            raise CCBashError(
                                f"stream readers did not finish after child exit; see {stdout_log} and {stderr_log}"
                            )
            except Exception:
                if process.poll() is None:
                    terminate_process_group(process, shutdown_timeout, wrapper_log)
                join_stream_threads(threads, shutdown_timeout)
                raise
        finally:
            if raw_events_file is not None:
                raw_events_file.close()
    append_wrapper_log(wrapper_log, f"completed_at: {utc_timestamp()}\nexit_code: {return_code}\n")
    return return_code


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
) -> None:
    """Copy child stdout into lean event logs while avoiding raw JSON duplication."""
    for chunk in source:
        first_output.set()
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
        with stderr_lock:
            sys.stderr.write(mirrored)
            sys.stderr.flush()


def tee_stderr_stream(
    source: TextIO,
    log_files: Sequence[TextIO],
    stderr_lock: Lock,
    first_output: Event,
) -> None:
    """Copy child stderr to logs and wrapper stderr."""
    for chunk in source:
        first_output.set()
        for log_file in log_files:
            log_file.write(chunk)
            log_file.flush()
        with stderr_lock:
            sys.stderr.write(chunk)
            sys.stderr.flush()


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


def enforce_startup_timeout(
    *,
    process: subprocess.Popen[str],
    first_output: Event,
    startup_timeout: float,
    stderr_file: TextIO,
    stderr_lock: Lock,
    wrapper_log: Path,
    shutdown_timeout: float,
) -> None:
    """Terminate a stream worker that never emits its first line."""
    if startup_timeout <= 0 or first_output.is_set():
        return

    deadline = time.monotonic() + startup_timeout
    while process.poll() is None and not first_output.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process_tree = format_process_tree(process.pid)
            message = (
                f"no child stdout/stderr after {startup_timeout:g}s in stream mode; "
                f"terminating process group {process.pid}\n{process_tree}\n"
            )
            emit_wrapper_diagnostic(message, stderr_file, stderr_lock, wrapper_log)
            terminate_process_group(process, shutdown_timeout, wrapper_log)
            raise CCBashError(
                f"Claude Code produced no stdout/stderr within {startup_timeout:g}s in stream mode; "
                "see wrapper/stderr logs"
            )
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
            raise CCBashError("process group did not exit after SIGKILL") from error


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
    append_system_prompt: str | None,
    skill_count: int,
    stdout_log: Path,
    stderr_log: Path,
    events_log: Path,
    raw_events_log: Path,
) -> None:
    """Write wrapper-side launch diagnostics before child output exists."""
    wrapper_log.parent.mkdir(parents=True, exist_ok=True)
    append_prompt_bytes = len(append_system_prompt.encode("utf-8")) if append_system_prompt else 0
    metadata = [
        f"started_at: {utc_timestamp()}",
        f"agent_id: {config.agent_id}",
        f"stream: {config.stream}",
        f"raw_events: {config.raw_events}",
        f"model: {config.model}",
        f"output_format: {config.output_format}",
        f"startup_timeout_seconds: {config.startup_timeout:g}",
        f"shutdown_timeout_seconds: {config.shutdown_timeout:g}",
        f"prompt_bytes: {len(prompt.encode('utf-8'))}",
        f"append_system_prompt_bytes: {append_prompt_bytes}",
        f"skill_count: {skill_count}",
        f"stdout_log: {stdout_log}",
        f"stderr_log: {stderr_log}",
        f"events_log: {events_log}",
        f"raw_events_log: {raw_events_log if config.raw_events else ''}",
        f"command: {render_command_preview(command)}",
        "",
    ]
    wrapper_log.write_text("\n".join(metadata), encoding="utf-8")


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
    redact_until_next_flag = False
    for value in command:
        if redact_until_next_flag and value.startswith("--"):
            redact_until_next_flag = False
        if redact_until_next_flag:
            redacted.append("<redacted>")
            continue
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        flag, separator, _secret = value.partition("=")
        if separator and flag in SENSITIVE_PROCESS_ARG_FLAGS:
            redacted.append(f"{flag}=<redacted>")
            continue
        redacted.append(value)
        if value in MULTI_VALUE_SENSITIVE_PROCESS_ARG_FLAGS:
            redact_until_next_flag = True
        elif value in SENSITIVE_PROCESS_ARG_FLAGS:
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


def build_claude_command(config: LaunchConfig, append_system_prompt: str | None, prompt: str) -> list[str]:
    """Build the shell-free Claude Code argv."""
    command = resolve_claude_command(config)
    command.extend(["--model", config.model, "--output-format", config.output_format])
    if config.stream:
        command.append("--verbose")
    if config.no_session_persistence:
        command.append("--no-session-persistence")
    if config.bare:
        command.append("--bare")
    if config.permission_mode:
        command.extend(["--permission-mode", config.permission_mode])
    if config.allowed_tools:
        command.extend(["--allowedTools", ",".join(config.allowed_tools)])
    if config.disallowed_tools:
        command.extend(["--disallowedTools", ",".join(config.disallowed_tools)])
    if config.add_dirs:
        command.append("--add-dir")
        command.extend(config.add_dirs)
    if config.mcp_configs:
        command.append("--mcp-config")
        command.extend(config.mcp_configs)
    if config.strict_mcp_config:
        command.append("--strict-mcp-config")
    if config.settings:
        command.extend(["--settings", config.settings])
    if config.setting_sources:
        command.extend(["--setting-sources", config.setting_sources])
    for plugin_dir in config.plugin_dirs:
        command.extend(["--plugin-dir", plugin_dir])
    if append_system_prompt:
        command.extend(["--append-system-prompt", append_system_prompt])
    command.extend(["-p", prompt])
    return command


def resolve_claude_command(config: LaunchConfig) -> list[str]:
    """Resolve Claude Code command, preferring claude and falling back to npx."""
    if config.claude_bin:
        return [config.claude_bin]

    resolved_claude = shutil.which("claude")
    if resolved_claude:
        return [resolved_claude]

    npx_bin = config.npx_bin or shutil.which("npx") or "npx"
    return [npx_bin, "-y", CLAUDE_CODE_NPX_PACKAGE]


def build_worker_prompt(config: LaunchConfig, skills: Sequence[ResolvedSkill]) -> str:
    """Synthesize the programmatic Claude Code worker prompt from wrapper arguments."""
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
        "# cc-bash worker protocol",
        "",
        "You are running as a Claude Code print-mode worker supervised by cc-bash.py.",
        "All substantive output must be written to the declared report file, not to chat/stdout.",
        "After successful report and signal creation, your final textual response must be exactly `0`.",
        "Wrapper validation, not raw Claude Code output, is authoritative.",
        "Do not launch nested subagents.",
        "Do not use control-plane bridge tools or `report_parent`.",
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
    lines.extend(build_skill_prompt_reference(skills))
    lines.extend(
        [
            "## Completion contract",
            "Return exactly `0` after the report and success signal are written.",
            "If you cannot complete the task, write a failure report if possible, do not create a success signal, and return non-zero text.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_skill_prompt_reference(skills: Sequence[ResolvedSkill]) -> list[str]:
    """Build user-prompt lines referencing appended preloaded skills."""
    if not skills:
        return [
            "## Preloaded skills",
            "No additional skills were requested for preload.",
            "",
        ]

    lines = [
        "## Preloaded skills",
        "The wrapper appended the following skill content to the system prompt in the order shown below.",
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


def build_append_system_prompt(
    skills: Sequence[ResolvedSkill],
    extra_append_system_prompts: Sequence[str],
) -> str | None:
    """Build append-only system prompt context for skill preload and caller additions."""
    blocks: list[str] = []
    if skills:
        lines = [
            "# cc-bash preloaded skills",
            "",
            "The following skills were resolved by cc-bash.py and appended without replacing the default Claude Code system prompt.",
            "Apply these skills in order before substantive work. The user prompt's file protocol remains mandatory.",
        ]
        for index, skill in enumerate(skills, start=1):
            lines.extend(
                [
                    "",
                    f"## Skill {index}: {skill.requested}",
                    f"- Resolved path: {skill.cli_path}",
                    f"- Content source: {skill.content_path}",
                    f"- Content SHA-256: {skill.content_sha256}",
                    "",
                    "```markdown",
                    skill.content_text.rstrip(),
                    "```",
                ]
            )
        blocks.append("\n".join(lines))

    blocks.extend(prompt for prompt in extra_append_system_prompts if prompt.strip())
    if not blocks:
        return None

    append_system_prompt = "\n\n".join(blocks).rstrip() + "\n"
    if len(append_system_prompt) > MAX_APPEND_SYSTEM_PROMPT_CHARS:
        raise CCBashError(
            "append system prompt exceeds safe argv size "
            f"({len(append_system_prompt)} > {MAX_APPEND_SYSTEM_PROMPT_CHARS} chars)"
        )
    return append_system_prompt


def resolve_skill(cwd: Path, requested: str) -> ResolvedSkill:
    """Resolve a skill name or path and verify readable content."""
    if not requested.strip():
        raise CCBashError("skill arguments must not be empty")

    path_candidate = expand_path_text(requested, cwd)
    if is_path_like(requested):
        if not path_candidate.exists():
            raise CCBashError(f"skill path does not exist: {requested}")
        return build_resolved_skill(requested, path_candidate)

    matches = find_named_skill_candidates(cwd, requested)
    unique_matches = dedupe_paths(matches)
    if not unique_matches:
        raise CCBashError(f"could not resolve skill by name: {requested}")
    if len(unique_matches) > 1:
        rendered_matches = ", ".join(str(path) for path in unique_matches)
        raise CCBashError(f"ambiguous skill name {requested!r}: {rendered_matches}")
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
        raise CCBashError(f"skill path is neither a file nor directory: {path}")

    try:
        content = content_path.read_bytes()
    except OSError as error:
        raise CCBashError(f"skill content is not readable: {content_path}: {error}") from error

    return ResolvedSkill(
        requested=requested,
        cli_path=cli_path,
        content_path=content_path,
        content_sha256=hashlib.sha256(content).hexdigest(),
        content_text=content.decode(errors="replace"),
    )


def skill_directory_content_path(path: Path) -> Path:
    """Choose the deterministic readable content file for a skill directory."""
    skill_md = path / "SKILL.md"
    if skill_md.exists():
        return skill_md
    markdown_files = sorted(child for child in path.iterdir() if child.is_file() and child.suffix == ".md")
    if not markdown_files:
        raise CCBashError(f"skill directory has no readable markdown entrypoint: {path}")
    return markdown_files[0]


def log_paths(cwd: Path, session_dir: str, agent_id: str) -> tuple[Path, Path, Path, Path, Path]:
    """Return stdout, stderr, lean event, raw event, and wrapper log paths for the worker."""
    session_abs = resolve_project_path(cwd, session_dir)
    safe_name = safe_log_name(agent_id)
    logs_dir = session_abs / "logs"
    return (
        logs_dir / f"{safe_name}.stdout.log",
        logs_dir / f"{safe_name}.stderr.log",
        logs_dir / f"{safe_name}.events.jsonl",
        logs_dir / f"{safe_name}.raw-events.jsonl",
        logs_dir / f"{safe_name}.wrapper.log",
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


def clear_previous_signal(signal_abs: Path) -> None:
    """Remove any prior signal so success must come from this launch."""
    if not signal_abs.exists():
        return
    if not signal_abs.is_file():
        raise CCBashError(f"declared signal path exists and is not a file: {signal_abs}")
    signal_abs.unlink()


def validate_protocol_outputs(
    *,
    report_abs: Path,
    signal_abs: Path,
    report_path_arg: str,
    cwd: Path,
) -> None:
    """Validate report and signal artifacts after Claude Code exits."""
    if not report_abs.exists() or not report_abs.is_file():
        raise CCBashError(f"missing report file: {report_abs}")
    if not signal_abs.exists() or not signal_abs.is_file():
        raise CCBashError(f"missing signal file: {signal_abs}")

    signal_values = parse_signal_file(signal_abs)
    if signal_values.get("status") != "success":
        raise CCBashError(f"signal status is not success: {signal_abs}")
    signal_report_path = signal_values.get("path")
    if signal_report_path is None:
        raise CCBashError(f"signal missing path field: {signal_abs}")
    if resolve_project_path(cwd, signal_report_path) != resolve_project_path(cwd, report_path_arg):
        raise CCBashError(
            f"signal path does not match declared report path: {signal_report_path} != {report_path_arg}"
        )

    report_text = report_abs.read_text(errors="replace")
    missing_headings = [heading for heading in REQUIRED_REPORT_HEADINGS if heading not in report_text]
    if missing_headings:
        raise CCBashError(f"report missing required headings: {', '.join(missing_headings)}")


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
