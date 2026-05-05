#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run a programmatic pi worker behind a file-based MUX-compatible contract."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Thread
from typing import Sequence, TextIO

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
    stream: bool
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
    launch_parser.add_argument("--stream", action="store_true", help="Stream raw pi JSON events to stderr and an events log")
    launch_parser.add_argument("--cwd", default=".", help="Project root / worker current directory")
    launch_parser.add_argument("--pi-bin", default="pi", help="pi executable path, primarily for tests")
    return parser


def launch_from_args(args: argparse.Namespace) -> int:
    """Validate arguments, launch pi, and validate the file protocol."""
    config = parse_launch_config(args)
    resolved_skills = tuple(resolve_skill(config.cwd, skill) for skill in config.skills)
    prompt = build_worker_prompt(config, resolved_skills)
    stdout_log, stderr_log, events_log = log_paths(config.cwd, config.session_dir, config.agent_id)
    report_abs = resolve_project_path(config.cwd, config.report_path)
    signal_abs = resolve_project_path(config.cwd, config.signal_path)
    clear_previous_signal(signal_abs)

    result = run_pi(config, resolved_skills, prompt, stdout_log, stderr_log, events_log)
    if result != 0:
        raise PiBashError(f"pi exited with code {result}; see {stdout_log} and {stderr_log}")

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
        stream=bool(args.stream),
        cwd=cwd,
        pi_bin=str(args.pi_bin),
    )


def run_pi(
    config: LaunchConfig,
    skills: Sequence[ResolvedSkill],
    prompt: str,
    stdout_log: Path,
    stderr_log: Path,
    events_log: Path,
) -> int:
    """Run the underlying pi process and persist raw output to log files."""
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stderr_log.parent.mkdir(parents=True, exist_ok=True)
    events_log.parent.mkdir(parents=True, exist_ok=True)

    command = build_pi_command(config, skills, prompt)
    if config.stream:
        return run_streaming_pi(command, config.cwd, stdout_log, stderr_log, events_log)

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
        stderr_log.write_text(f"failed to execute pi: {error}\n")
        raise PiBashError(f"failed to execute pi: {error}") from error

    stdout_log.write_text(result.stdout)
    stderr_log.write_text(result.stderr)
    return result.returncode


def build_pi_command(config: LaunchConfig, skills: Sequence[ResolvedSkill], prompt: str) -> list[str]:
    """Build the shell-free pi argv."""
    command = [config.pi_bin]
    if config.stream:
        command.extend(["--mode", "json"])
    command.extend(["--model", config.model])
    if config.thinking:
        command.extend(["--thinking", config.thinking])
    for skill in skills:
        command.extend(["--skill", str(skill.cli_path)])
    command.extend(["-p", prompt])
    return command


def run_streaming_pi(command: Sequence[str], cwd: Path, stdout_log: Path, stderr_log: Path, events_log: Path) -> int:
    """Run pi while teeing child streams to logs and wrapper stderr."""
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        stdout_log.write_text("")
        stderr_log.write_text(f"failed to execute pi: {error}\n")
        events_log.write_text("")
        raise PiBashError(f"failed to execute pi: {error}") from error

    if process.stdout is None or process.stderr is None:
        raise PiBashError("failed to capture pi stdout/stderr")

    stderr_lock = Lock()
    with stdout_log.open("w", encoding="utf-8", buffering=1) as stdout_file, stderr_log.open(
        "w",
        encoding="utf-8",
        buffering=1,
    ) as stderr_file, events_log.open("w", encoding="utf-8", buffering=1) as events_file:
        stdout_thread = Thread(
            target=tee_child_stream,
            args=(process.stdout, (stdout_file, events_file), stderr_lock),
            daemon=True,
        )
        stderr_thread = Thread(
            target=tee_child_stream,
            args=(process.stderr, (stderr_file,), stderr_lock),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        return_code = process.wait()
        stdout_thread.join()
        stderr_thread.join()
    return return_code


def tee_child_stream(source: TextIO, log_files: Sequence[TextIO], stderr_lock: Lock) -> None:
    """Copy one child stream to log files and wrapper stderr line by line."""
    for chunk in source:
        for log_file in log_files:
            log_file.write(chunk)
            log_file.flush()
        with stderr_lock:
            sys.stderr.write(chunk)
            sys.stderr.flush()


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


def log_paths(cwd: Path, session_dir: str, agent_id: str) -> tuple[Path, Path, Path]:
    """Return stdout, stderr, and event log paths for the worker."""
    session_abs = resolve_project_path(cwd, session_dir)
    safe_name = safe_log_name(agent_id)
    logs_dir = session_abs / "logs"
    return (
        logs_dir / f"{safe_name}.stdout.log",
        logs_dir / f"{safe_name}.stderr.log",
        logs_dir / f"{safe_name}.events.jsonl",
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
        raise PiBashError(f"declared signal path exists and is not a file: {signal_abs}")
    signal_abs.unlink()


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
