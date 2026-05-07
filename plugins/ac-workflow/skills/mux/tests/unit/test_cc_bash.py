#!/usr/bin/env python3
"""Unit tests for the cc-bash supervised Claude Code launcher."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[6]
CC_BASH = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux" / "tools" / "cc-bash.py"


FAKE_CLAUDE = f'''#!{sys.executable}
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    argv_path = Path(os.environ["FAKE_CC_ARGV_PATH"])
    prompt_path = Path(os.environ["FAKE_CC_PROMPT_PATH"])
    argv_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    argv_path.write_text(json.dumps(sys.argv[1:], indent=2))

    try:
        prompt = sys.argv[sys.argv.index("-p") + 1]
    except (ValueError, IndexError):
        prompt = sys.argv[-1] if sys.argv[1:] else ""
    prompt_path.write_text(prompt)

    sleep_before_output = float(os.environ.get("FAKE_CC_SLEEP_BEFORE_OUTPUT", "0"))
    if sleep_before_output:
        time.sleep(sleep_before_output)

    stream_mode = "--output-format" in sys.argv and sys.argv[sys.argv.index("--output-format") + 1] == "stream-json"
    if os.environ.get("FAKE_CC_SPAWN_PIPE_HOLDER", "0") == "1":
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])

    if stream_mode:
        print(json.dumps({{"type": "message_start", "message": "hello"}}), flush=True)
        if os.environ.get("FAKE_CC_SENSITIVE_EVENT", "0") == "1":
            print(
                json.dumps(
                    {{
                        "type": "message_update",
                        "message": {{
                            "content": [{{"type": "text", "text": "secret prompt text"}}],
                            "thinkingSignature": "encrypted-signature-value",
                        }},
                    }}
                ),
                flush=True,
            )
        print(json.dumps({{"type": "tool_use", "name": "Read"}}), flush=True)
        if os.environ.get("FAKE_CC_PRETOOL_STDERR", "0") == "1":
            print("PreToolUse:Bash says:", file=sys.stderr, flush=True)
        print("fake claude stream stderr", file=sys.stderr, flush=True)
    else:
        print("fake claude stdout")
        print("fake claude stderr", file=sys.stderr)

    if os.environ.get("FAKE_CC_EXIT", "0") != "0":
        return int(os.environ["FAKE_CC_EXIT"])

    if os.environ.get("FAKE_CC_WRITE_ARTIFACTS", "1") != "1":
        return 0

    report_match = re.search(r"Report path: `([^`]+)`", prompt)
    signal_match = re.search(r"Signal path: `([^`]+)`", prompt)
    if report_match is None or signal_match is None:
        return 7

    report_rel = report_match.group(1)
    signal_rel = signal_match.group(1)
    report_path = Path(report_rel)
    signal_path = Path(signal_rel)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    signal_path.parent.mkdir(parents=True, exist_ok=True)

    if os.environ.get("FAKE_CC_BAD_REPORT", "0") == "1":
        report_path.write_text("# Worker Report\\n\\n## Executive Summary\\nIncomplete\\n")
    else:
        report_path.write_text(
            "# Worker Report\\n\\n"
            "## Table of Contents\\n"
            "- Executive Summary\\n\\n"
            "## Executive Summary\\n"
            "Completed safely.\\n\\n"
            "### Next Steps\\n"
            "- Continue.\\n"
        )

    if os.environ.get("FAKE_CC_WRITE_SIGNAL", "1") == "1":
        signal_path.write_text(
            f"path: {{report_rel}}\\n"
            "size: 10\\n"
            "status: success\\n"
            "created_at: 2026-05-05T00:00:00+00:00\\n"
        )
    if os.environ.get("FAKE_CC_EXIT_AFTER_ARTIFACTS", "0") != "0":
        return int(os.environ["FAKE_CC_EXIT_AFTER_ARTIFACTS"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_fake_executable(tmp_path: Path, name: str) -> Path:
    """Write an executable fake Claude Code or npx binary."""
    fake_executable = tmp_path / "bin" / name
    fake_executable.parent.mkdir(parents=True, exist_ok=True)
    fake_executable.write_text(FAKE_CLAUDE)
    fake_executable.chmod(0o755)
    return fake_executable


def create_workspace(tmp_path: Path) -> Path:
    """Create a project-like workspace with named and path-form skills."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    skill_dir = workspace / ".claude" / "skills" / "builder"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: builder\n"
        "description: Example builder skill.\n"
        "---\n\n"
        "# Builder\n\n"
        "Follow the file protocol.\n"
    )
    (workspace / "sentinel.md").write_text("# Sentinel\n\nReview carefully.\n")
    (workspace / "settings.json").write_text("{}\n")
    (workspace / "mcp.json").write_text("{}\n")
    (workspace / "plugin-dir").mkdir()
    return workspace


def run_cc_bash(
    *,
    workspace: Path,
    tmp_path: Path,
    path_value: str,
    extra_args: Sequence[str] = (),
    env_overrides: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run cc-bash with a deterministic baseline command."""
    env = os.environ.copy()
    env.update(
        {
            "FAKE_CC_ARGV_PATH": str(tmp_path / "fake" / "argv.json"),
            "FAKE_CC_PROMPT_PATH": str(tmp_path / "fake" / "prompt.md"),
            "PATH": path_value,
        }
    )
    if env_overrides:
        env.update(env_overrides)

    command = [
        sys.executable,
        str(CC_BASH),
        "launch",
        "tmp/mux/session",
        "agent-1",
        "--role",
        "project-defined reviewer role",
        "--worker-type",
        "reviewer-like",
        "--objective",
        "review a bounded change",
        "--scope",
        "workspace only",
        "--task",
        "Write the report and signal files.",
        "--report-path",
        "tmp/mux/session/review/agent-1.md",
        "--signal-path",
        "tmp/mux/session/.signals/agent-1.done",
        "--model",
        "opus",
        "--permission-mode",
        "acceptEdits",
        "--allowed-tool",
        "Read",
        "--allowed-tool",
        "Write",
        "--disallowed-tool",
        "Task",
        "--add-dir",
        str(workspace),
        "--mcp-config",
        str(workspace / "mcp.json"),
        "--strict-mcp-config",
        "--settings",
        str(workspace / "settings.json"),
        "--setting-sources",
        "project",
        "--plugin-dir",
        str(workspace / "plugin-dir"),
        "--append-system-prompt",
        "Additional append-only guidance.",
        "--bare",
        "--skill",
        "builder",
        "--skill",
        str(workspace / "sentinel.md"),
        "--cwd",
        str(workspace),
        *extra_args,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False, env=env)


def test_cc_bash_success_uses_resolved_claude_and_expands_prompt(tmp_path: Path) -> None:
    """Successful workers produce exact stdout, logs, argv, report, and signal evidence."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(workspace=workspace, tmp_path=tmp_path, path_value=str(fake_claude.parent))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert result.stderr == ""

    stdout_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.stdout.log"
    stderr_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.stderr.log"
    events_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.events.jsonl"
    wrapper_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.wrapper.log"
    assert stdout_log.read_text() == "fake claude stdout\n"
    assert stderr_log.read_text() == "fake claude stderr\n"
    assert not events_log.exists()
    wrapper_text = wrapper_log.read_text()
    assert "prompt_bytes:" in wrapper_text
    assert "append_system_prompt_bytes:" in wrapper_text
    assert "skill_count: 2" in wrapper_text
    assert "command:" in wrapper_text
    assert "<redacted>" in wrapper_text
    assert "Additional append-only guidance." not in wrapper_text
    assert "Write the report and signal files." not in wrapper_text

    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert argv[:5] == ["--model", "opus", "--output-format", "text", "--no-session-persistence"]
    assert "--bare" in argv
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--permission-mode"] == ["acceptEdits"]
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--allowedTools"] == ["Read,Write"]
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--disallowedTools"] == ["Task"]
    assert "--add-dir" in argv
    assert str(workspace) in argv
    assert "--mcp-config" in argv
    assert str(workspace / "mcp.json") in argv
    assert "--strict-mcp-config" in argv
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--settings"] == [
        str(workspace / "settings.json")
    ]
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--setting-sources"] == ["project"]
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--plugin-dir"] == [
        str(workspace / "plugin-dir")
    ]
    assert "--system-prompt" not in argv
    assert "--append-system-prompt" in argv
    append_prompt = argv[argv.index("--append-system-prompt") + 1]
    assert "# cc-bash preloaded skills" in append_prompt
    assert "## Skill 1: builder" in append_prompt
    assert "# Builder" in append_prompt
    assert "## Skill 2:" in append_prompt
    assert "# Sentinel" in append_prompt
    assert "Additional append-only guidance." in append_prompt

    prompt = (tmp_path / "fake" / "prompt.md").read_text()
    assert "Role: project-defined reviewer role" in prompt
    assert "Worker type: reviewer-like" in prompt
    assert "Report path: `tmp/mux/session/review/agent-1.md`" in prompt
    assert "Signal path: `tmp/mux/session/.signals/agent-1.done`" in prompt
    assert "Wrapper validation, not raw Claude Code output, is authoritative." in prompt
    assert "final textual response must be exactly `0`" in prompt


def test_cc_bash_stream_overrides_output_format_and_tees_events(tmp_path: Path) -> None:
    """Streaming workers force stream-json while keeping wrapper stdout exactly zero."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        extra_args=["--output-format", "json", "--stream"],
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert '"type":"message_start"' in result.stderr
    assert '"type":"tool_use"' in result.stderr
    assert "cc> fake claude stream stderr" in result.stderr

    stdout_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.stdout.log"
    stderr_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.stderr.log"
    events_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.events.jsonl"
    raw_events_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.raw-events.jsonl"
    assert "stream stdout JSON events are captured as lean events" in stdout_log.read_text()
    assert not raw_events_log.exists()
    events = [json.loads(line) for line in events_log.read_text().splitlines()]
    assert [event["type"] for event in events] == ["message_start", "tool_use"]
    assert stderr_log.read_text() == "fake claude stream stderr\n"

    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert argv[:4] == ["--model", "opus", "--output-format", "stream-json"]
    assert "--verbose" in argv


def test_cc_bash_stream_prefixes_child_hook_stderr(tmp_path: Path) -> None:
    """Mirrored child hook output is attributable to the inner Claude Code worker."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        extra_args=["--stream"],
        env_overrides={"FAKE_CC_PRETOOL_STDERR": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "cc> PreToolUse:Bash says:" in result.stderr
    stderr_text = (workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.stderr.log").read_text()
    assert "PreToolUse:Bash says:" in stderr_text
    assert "cc> PreToolUse:Bash says:" not in stderr_text


def test_cc_bash_stream_no_mirror_preserves_logs(tmp_path: Path) -> None:
    """No-mirror mode suppresses live child output while keeping logs and events."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        extra_args=["--stream", "--no-mirror"],
    )

    logs_dir = workspace / "tmp" / "mux" / "session" / "logs"
    assert result.returncode == 0, result.stderr
    assert '"type":"message_start"' not in result.stderr
    assert "fake claude stream stderr" not in result.stderr
    assert '"type":"message_start"' in (logs_dir / "agent-1.events.jsonl").read_text()
    assert "fake claude stream stderr\n" in (logs_dir / "agent-1.stderr.log").read_text()


def test_cc_bash_stream_sanitizes_events_with_raw_opt_in(tmp_path: Path) -> None:
    """Lean events omit bulky/sensitive payloads while raw events remain explicit opt-in."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        extra_args=["--stream", "--raw-events"],
        env_overrides={"FAKE_CC_SENSITIVE_EVENT": "1"},
    )

    assert result.returncode == 0, result.stderr
    logs_dir = workspace / "tmp" / "mux" / "session" / "logs"
    events_text = (logs_dir / "agent-1.events.jsonl").read_text()
    raw_events_text = (logs_dir / "agent-1.raw-events.jsonl").read_text()
    stdout_text = (logs_dir / "agent-1.stdout.log").read_text()

    assert "secret prompt text" not in events_text
    assert "encrypted-signature-value" not in events_text
    assert '\"redacted\":\"object\"' in events_text
    assert "secret prompt text" in raw_events_text
    assert "encrypted-signature-value" in raw_events_text
    assert "secret prompt text" not in stdout_text
    assert "raw stream stdout is captured" in stdout_text


def test_cc_bash_stream_cleans_up_inherited_pipe_descendants(tmp_path: Path) -> None:
    """Exited workers do not hang forever when descendants inherit stdout/stderr pipes."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        extra_args=["--stream", "--shutdown-timeout", "0.1"],
        env_overrides={"FAKE_CC_SPAWN_PIPE_HOLDER": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert "stream readers did not finish after child exit" in result.stderr

    wrapper_text = (workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.wrapper.log").read_text()
    assert "process_group_id:" in wrapper_text
    assert "exit_code: 0" in wrapper_text


def test_cc_bash_stream_warns_without_killing_when_child_delays_first_event(tmp_path: Path) -> None:
    """Streaming workers warn on startup silence without killing a healthy child."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        extra_args=["--stream", "--startup-warn-after", "0.1", "--shutdown-timeout", "0.1"],
        env_overrides={"FAKE_CC_SLEEP_BEFORE_OUTPUT": "0.2"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert "no child stdout/stderr after 0.1s in stream mode" in result.stderr
    assert "continuing without terminating process group" in result.stderr
    assert "process_tree:" in result.stderr

    logs_dir = workspace / "tmp" / "mux" / "session" / "logs"
    assert '"type":"message_start"' in (logs_dir / "agent-1.events.jsonl").read_text()
    wrapper_text = (logs_dir / "agent-1.wrapper.log").read_text()
    assert "child_pid:" in wrapper_text
    assert "command:" in wrapper_text
    assert "<redacted>" in wrapper_text
    assert "Additional append-only guidance." not in wrapper_text
    assert "Write the report and signal files." not in wrapper_text


def test_cc_bash_falls_back_to_npx_package_when_claude_is_unavailable(tmp_path: Path) -> None:
    """When claude is not on PATH, the wrapper falls back to npx Claude Code package execution."""
    workspace = create_workspace(tmp_path)
    fake_npx = write_fake_executable(tmp_path, "npx")

    result = run_cc_bash(workspace=workspace, tmp_path=tmp_path, path_value=str(fake_npx.parent))

    assert result.returncode == 0, result.stderr
    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert argv[:4] == ["-y", "@anthropic-ai/claude-code", "--model", "opus"]


def test_cc_bash_nonzero_child_with_valid_protocol_succeeds(tmp_path: Path) -> None:
    """A valid report and success signal are authoritative over child exit code."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        env_overrides={"FAKE_CC_EXIT_AFTER_ARTIFACTS": "3"},
    )

    logs_dir = workspace / "tmp" / "mux" / "session" / "logs"
    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert "protocol valid; treating child issue as success" in (logs_dir / "agent-1.stderr.log").read_text()
    assert "child_exit_code=3" in (logs_dir / "agent-1.wrapper.log").read_text()


def test_cc_bash_clears_stale_protocol_artifacts_before_launch(tmp_path: Path) -> None:
    """Stale report and signal files cannot satisfy a later launch."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")
    report_path = workspace / "tmp" / "mux" / "session" / "review" / "agent-1.md"
    signal_path = workspace / "tmp" / "mux" / "session" / ".signals" / "agent-1.done"
    report_path.parent.mkdir(parents=True)
    signal_path.parent.mkdir(parents=True)
    report_path.write_text(
        "# Worker Report\n\n"
        "## Table of Contents\n"
        "- Executive Summary\n\n"
        "## Executive Summary\n"
        "Stale.\n\n"
        "### Next Steps\n"
        "- Continue.\n"
    )
    signal_path.write_text("path: tmp/mux/session/review/agent-1.md\nstatus: success\n")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        env_overrides={"FAKE_CC_WRITE_ARTIFACTS": "0"},
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "missing report file" in result.stderr
    assert not report_path.exists()
    assert not signal_path.exists()


GENERIC_FAILURE_CASES = [
    (
        "missing signal",
        {"FAKE_CC_WRITE_SIGNAL": "0"},
        "missing signal file",
    ),
    (
        "bad report",
        {"FAKE_CC_BAD_REPORT": "1"},
        "report missing required headings",
    ),
    (
        "child nonzero",
        {"FAKE_CC_EXIT": "3"},
        "Claude Code exited with code 3",
    ),
]


def test_cc_bash_fail_closed_cases(tmp_path: Path) -> None:
    """Missing artifacts, invalid reports, and non-zero child exits fail closed."""
    for case_name, env_overrides, expected_error in GENERIC_FAILURE_CASES:
        case_tmp = tmp_path / case_name.replace(" ", "-")
        case_tmp.mkdir()
        workspace = create_workspace(case_tmp)
        fake_claude = write_fake_executable(case_tmp, "claude")

        result = run_cc_bash(
            workspace=workspace,
            tmp_path=case_tmp,
            path_value=str(fake_claude.parent),
            env_overrides=env_overrides,
        )

        assert result.returncode != 0, case_name
        assert result.stdout == ""
        assert expected_error in result.stderr


def test_cc_bash_unresolved_skill_fails_before_launch(tmp_path: Path) -> None:
    """Skill preload resolution is fail-closed and occurs before launching Claude Code."""
    workspace = create_workspace(tmp_path)
    fake_claude = write_fake_executable(tmp_path, "claude")

    result = run_cc_bash(
        workspace=workspace,
        tmp_path=tmp_path,
        path_value=str(fake_claude.parent),
        extra_args=["--skill", "does-not-exist"],
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "could not resolve skill by name: does-not-exist" in result.stderr
    assert not (tmp_path / "fake" / "argv.json").exists()


def test_cc_bash_help_documents_required_role() -> None:
    """The role remains a caller-provided argument rather than a hard-coded enum."""
    result = subprocess.run(
        [sys.executable, str(CC_BASH), "launch", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--role" in result.stdout
    assert "Project-defined opaque role label" in result.stdout
    assert "choices" not in result.stdout
