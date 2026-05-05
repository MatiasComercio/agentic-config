#!/usr/bin/env python3
"""Unit tests for the pi-bash supervised worker launcher."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[6]
PI_BASH = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux" / "tools" / "pi-bash.py"
ATTEMPT_ID = "attempt-1"


def log_path(workspace: Path, name: str) -> Path:
    """Return the deterministic attempt-scoped log path for the test worker."""
    return workspace / "tmp" / "mux" / "session" / "logs" / f"agent-1.{ATTEMPT_ID}.{name}"


FAKE_PI = r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    argv_path = Path(os.environ["FAKE_PI_ARGV_PATH"])
    prompt_path = Path(os.environ["FAKE_PI_PROMPT_PATH"])
    argv_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    argv_path.write_text(json.dumps(sys.argv[1:], indent=2))

    try:
        prompt = sys.argv[sys.argv.index("-p") + 1]
    except (ValueError, IndexError):
        prompt = ""
    prompt_path.write_text(prompt)

    sleep_before_output = float(os.environ.get("FAKE_PI_SLEEP_BEFORE_OUTPUT", "0"))
    if sleep_before_output:
        time.sleep(sleep_before_output)

    stream_mode = "--mode" in sys.argv and sys.argv[sys.argv.index("--mode") + 1] == "json"
    if os.environ.get("FAKE_PI_SPAWN_PIPE_HOLDER", "0") == "1":
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])

    if stream_mode:
        print(json.dumps({"type": "agent_start", "agent_id": "agent-1"}), flush=True)
        if os.environ.get("FAKE_PI_SENSITIVE_EVENT", "0") == "1":
            print(
                json.dumps(
                    {
                        "type": "message_update",
                        "message": {
                            "content": [{"type": "text", "text": "secret prompt text"}],
                            "thinkingSignature": "encrypted-signature-value",
                        },
                    }
                ),
                flush=True,
            )
        print(json.dumps({"type": "tool_execution_start", "tool": "Read"}), flush=True)
        print("fake stream stderr", file=sys.stderr, flush=True)
    else:
        print("fake stdout")
        print("fake stderr", file=sys.stderr)

    if os.environ.get("FAKE_PI_EXIT", "0") != "0":
        return int(os.environ["FAKE_PI_EXIT"])

    if os.environ.get("FAKE_PI_WRITE_ARTIFACTS", "1") != "1":
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

    if os.environ.get("FAKE_PI_BAD_REPORT", "0") == "1":
        report_path.write_text("# Worker Report\n\n## Executive Summary\nIncomplete\n")
    else:
        report_path.write_text(
            "# Worker Report\n\n"
            "## Table of Contents\n"
            "- Executive Summary\n\n"
            "## Executive Summary\n"
            "Completed safely.\n\n"
            "### Next Steps\n"
            "- Continue.\n"
        )

    if os.environ.get("FAKE_PI_WRITE_SIGNAL", "1") == "1":
        signal_path.write_text(
            f"path: {report_rel}\n"
            "size: 10\n"
            "status: success\n"
            "created_at: 2026-05-05T00:00:00+00:00\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_fake_pi(tmp_path: Path) -> Path:
    """Write an executable fake pi binary."""
    fake_pi = tmp_path / "bin" / "pi"
    fake_pi.parent.mkdir(parents=True, exist_ok=True)
    fake_pi.write_text(FAKE_PI)
    fake_pi.chmod(0o755)
    return fake_pi


def create_workspace(tmp_path: Path) -> Path:
    """Create a project-like workspace with a named skill."""
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
    return workspace


def run_pi_bash(
    *,
    workspace: Path,
    fake_pi: Path,
    tmp_path: Path,
    extra_args: Sequence[str] = (),
    env_overrides: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run pi-bash with a deterministic baseline command."""
    env = os.environ.copy()
    env.update(
        {
            "FAKE_PI_ARGV_PATH": str(tmp_path / "fake" / "argv.json"),
            "FAKE_PI_PROMPT_PATH": str(tmp_path / "fake" / "prompt.md"),
        }
    )
    if env_overrides:
        env.update(env_overrides)

    command = [
        sys.executable,
        str(PI_BASH),
        "launch",
        "tmp/mux/session",
        "agent-1",
        "--role",
        "project-defined builder role",
        "--worker-type",
        "builder-like",
        "--objective",
        "implement a bounded change",
        "--scope",
        "workspace only",
        "--task",
        "Write the report and signal files.",
        "--report-path",
        "tmp/mux/session/build/agent-1.md",
        "--signal-path",
        "tmp/mux/session/.signals/agent-1.done",
        "--model",
        "example/model-tier",
        "--thinking",
        "xhigh",
        "--skill",
        "builder",
        "--skill",
        str(workspace / "sentinel.md"),
        "--cwd",
        str(workspace),
        "--pi-bin",
        str(fake_pi),
        "--attempt-id",
        ATTEMPT_ID,
        *extra_args,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False, env=env)


def test_pi_bash_success_prints_zero_persists_logs_and_expands_prompt(tmp_path: Path) -> None:
    """Successful workers produce exact stdout, logs, argv, report, and signal evidence."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(workspace=workspace, fake_pi=fake_pi, tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert "pi-bash: spawned pid=" in result.stderr

    stdout_log = log_path(workspace, "stdout.log")
    stderr_log = log_path(workspace, "stderr.log")
    events_log = log_path(workspace, "events.jsonl")
    wrapper_log = log_path(workspace, "wrapper.log")
    assert stdout_log.read_text() == "fake stdout\n"
    assert "fake stderr\n" in stderr_log.read_text()
    assert not events_log.exists()
    wrapper_text = wrapper_log.read_text()
    assert "prompt_bytes:" in wrapper_text
    assert "command:" in wrapper_text
    assert "<redacted>" in wrapper_text
    assert "Write the report and signal files." not in wrapper_text

    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert argv[:6] == ["--no-extensions", "--tools", "read,bash,edit,write,grep,find,ls", "--model", "example/model-tier", "--thinking"]
    assert argv[6] == "xhigh"
    skill_args = [argv[index + 1] for index, value in enumerate(argv) if value == "--skill"]
    assert skill_args == [
        str(workspace / ".claude" / "skills" / "builder" / "SKILL.md"),
        str(workspace / "sentinel.md"),
    ]

    prompt = (tmp_path / "fake" / "prompt.md").read_text()
    assert "Role: project-defined builder role" in prompt
    assert "Worker type: builder-like" in prompt
    assert "Report path: `tmp/mux/session/build/agent-1.md`" in prompt
    assert "Signal path: `tmp/mux/session/.signals/agent-1.done`" in prompt
    assert "Requested: `builder`" in prompt
    assert f"Resolved path: `{workspace / '.claude' / 'skills' / 'builder' / 'SKILL.md'}`" in prompt
    assert f"Requested: `{workspace / 'sentinel.md'}`" in prompt
    assert "Content SHA-256:" in prompt
    assert "final textual response must be exactly `0`" in prompt


def test_pi_bash_stream_tees_events_to_logs_and_wrapper_stderr(tmp_path: Path) -> None:
    """Streaming workers preserve stdout protocol while exposing child JSONL live on stderr."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(workspace=workspace, fake_pi=fake_pi, tmp_path=tmp_path, extra_args=["--stream"])

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert '"type":"agent_start"' in result.stderr
    assert '"type":"tool_execution_start"' in result.stderr
    assert "fake stream stderr" in result.stderr

    stdout_log = log_path(workspace, "stdout.log")
    stderr_log = log_path(workspace, "stderr.log")
    events_log = log_path(workspace, "events.jsonl")
    raw_events_log = log_path(workspace, "raw-events.jsonl")
    assert "stream stdout JSON events are captured as lean events" in stdout_log.read_text()
    assert not raw_events_log.exists()
    events = [json.loads(line) for line in events_log.read_text().splitlines()]
    assert [event["type"] for event in events] == ["agent_start", "tool_execution_start"]
    assert "fake stream stderr\n" in stderr_log.read_text()

    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert argv[:5] == ["--mode", "json", "--no-extensions", "--tools", "read,bash,edit,write,grep,find,ls"]


def test_pi_bash_stream_sanitizes_events_with_raw_opt_in(tmp_path: Path) -> None:
    """Lean events omit bulky/sensitive payloads while raw events remain explicit opt-in."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream", "--raw-events"],
        env_overrides={"FAKE_PI_SENSITIVE_EVENT": "1"},
    )

    assert result.returncode == 0, result.stderr
    events_text = log_path(workspace, "events.jsonl").read_text()
    raw_events_text = log_path(workspace, "raw-events.jsonl").read_text()
    stdout_text = log_path(workspace, "stdout.log").read_text()

    assert "secret prompt text" not in events_text
    assert "encrypted-signature-value" not in events_text
    assert '"redacted":"object"' in events_text
    assert "secret prompt text" in raw_events_text
    assert "encrypted-signature-value" in raw_events_text
    assert "secret prompt text" not in stdout_text
    assert "raw stream stdout is captured" in stdout_text


def test_pi_bash_stream_waits_by_default_for_delayed_first_event(tmp_path: Path) -> None:
    """Default stream mode does not kill a healthy child before its first JSON event."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream"],
        env_overrides={"FAKE_PI_SLEEP_BEFORE_OUTPUT": "0.2"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert '"type":"agent_start"' in log_path(workspace, "events.jsonl").read_text()


def test_pi_bash_non_stream_emits_hang_snapshot_without_killing_by_default(tmp_path: Path) -> None:
    """Non-stream workers produce diagnostics while waiting through child silence."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--heartbeat-interval", "0.1", "--hang-snapshot-after", "0.1"],
        env_overrides={"FAKE_PI_SLEEP_BEFORE_OUTPUT": "0.3"},
    )

    assert result.returncode == 0, result.stderr
    wrapper_text = log_path(workspace, "wrapper.log").read_text()
    assert "pi-bash snapshot: child still running" in wrapper_text
    assert "process_tree:" in wrapper_text


def test_pi_bash_preserves_attempt_logs_and_updates_latest_manifest(tmp_path: Path) -> None:
    """Retries with the same agent id keep prior evidence instead of overwriting logs."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    first = run_pi_bash(workspace=workspace, fake_pi=fake_pi, tmp_path=tmp_path)
    second = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--attempt-id", "attempt-2"],
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert log_path(workspace, "wrapper.log").exists()
    assert (workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.attempt-2.wrapper.log").exists()
    latest = json.loads((workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.latest.json").read_text())
    assert latest["attempt_id"] == "attempt-2"


def test_pi_bash_stream_cleans_up_inherited_pipe_descendants(tmp_path: Path) -> None:
    """Exited workers do not hang forever when descendants inherit stdout/stderr pipes."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream", "--shutdown-timeout", "0.1"],
        env_overrides={"FAKE_PI_SPAWN_PIPE_HOLDER": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert "stream readers did not finish after child exit" in result.stderr

    wrapper_text = log_path(workspace, "wrapper.log").read_text()
    assert "process_group_id:" in wrapper_text
    assert "exit_code: 0" in wrapper_text


def test_pi_bash_stream_fails_fast_when_child_never_emits_first_event(tmp_path: Path) -> None:
    """Streaming workers get a startup watchdog instead of silent empty events logs."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream", "--startup-timeout", "0.1", "--shutdown-timeout", "0.1"],
        env_overrides={"FAKE_PI_SLEEP_BEFORE_OUTPUT": "5"},
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "pi produced no stdout/stderr within 0.1s in stream mode" in result.stderr
    assert "process_tree:" in result.stderr

    assert log_path(workspace, "events.jsonl").read_text() == ""
    assert "no child stdout/stderr after 0.1s" in log_path(workspace, "stderr.log").read_text()
    wrapper_text = log_path(workspace, "wrapper.log").read_text()
    assert "child_pid:" in wrapper_text
    assert "command:" in wrapper_text
    assert "<redacted>" in wrapper_text
    assert "Write the report and signal files." not in wrapper_text


GENERIC_FAILURE_CASES = [
    (
        "missing signal",
        {"FAKE_PI_WRITE_SIGNAL": "0"},
        "missing signal file",
    ),
    (
        "bad report",
        {"FAKE_PI_BAD_REPORT": "1"},
        "report missing required headings",
    ),
    (
        "child nonzero",
        {"FAKE_PI_EXIT": "3"},
        "pi exited with code 3",
    ),
]


def test_pi_bash_fail_closed_cases(tmp_path: Path) -> None:
    """Missing artifacts, invalid reports, and non-zero child exits fail closed."""
    for case_name, env_overrides, expected_error in GENERIC_FAILURE_CASES:
        case_tmp = tmp_path / case_name.replace(" ", "-")
        case_tmp.mkdir()
        workspace = create_workspace(case_tmp)
        fake_pi = write_fake_pi(case_tmp)

        result = run_pi_bash(
            workspace=workspace,
            fake_pi=fake_pi,
            tmp_path=case_tmp,
            env_overrides=env_overrides,
        )

        assert result.returncode != 0, case_name
        assert result.stdout == ""
        assert expected_error in result.stderr


def test_pi_bash_unresolved_skill_fails_before_launch(tmp_path: Path) -> None:
    """Skill preload resolution is fail-closed and occurs before launching pi."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--skill", "does-not-exist"],
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "could not resolve skill by name: does-not-exist" in result.stderr
    assert not (tmp_path / "fake" / "argv.json").exists()


def test_pi_bash_help_documents_required_role() -> None:
    """The role remains a caller-provided argument rather than a hard-coded enum."""
    result = subprocess.run(
        [sys.executable, str(PI_BASH), "launch", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--role" in result.stdout
    assert "Project-defined opaque role label" in result.stdout
    assert "choices" not in result.stdout
