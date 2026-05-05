#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run a Claude Code print-mode worker behind a file-based contract."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

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


def launch_from_args(args: argparse.Namespace) -> int:
    """Validate arguments, launch Claude Code, and validate the file protocol."""
    config = parse_launch_config(args)
    resolved_skills = tuple(resolve_skill(config.cwd, skill) for skill in config.skills)
    prompt = build_worker_prompt(config, resolved_skills)
    append_system_prompt = build_append_system_prompt(resolved_skills, config.append_system_prompts)
    stdout_log, stderr_log = log_paths(config.cwd, config.session_dir, config.agent_id)
    report_abs = resolve_project_path(config.cwd, config.report_path)
    signal_abs = resolve_project_path(config.cwd, config.signal_path)
    clear_previous_signal(signal_abs)

    result = run_claude(config, append_system_prompt, prompt, stdout_log, stderr_log)
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
        output_format=str(args.output_format),
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
) -> int:
    """Run the underlying Claude Code process and persist raw output to log files."""
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stderr_log.parent.mkdir(parents=True, exist_ok=True)

    command = build_claude_command(config, append_system_prompt, prompt)
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
        raise CCBashError(f"failed to execute Claude Code: {error}") from error

    stdout_log.write_text(result.stdout)
    stderr_log.write_text(result.stderr)
    return result.returncode


def build_claude_command(config: LaunchConfig, append_system_prompt: str | None, prompt: str) -> list[str]:
    """Build the shell-free Claude Code argv."""
    command = resolve_claude_command(config)
    command.extend(["--model", config.model, "--output-format", config.output_format])
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


def log_paths(cwd: Path, session_dir: str, agent_id: str) -> tuple[Path, Path]:
    """Return stdout/stderr log paths for the worker."""
    session_abs = resolve_project_path(cwd, session_dir)
    safe_name = safe_log_name(agent_id)
    logs_dir = session_abs / "logs"
    return logs_dir / f"{safe_name}.stdout.log", logs_dir / f"{safe_name}.stderr.log"


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
