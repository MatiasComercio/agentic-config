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
        if os.environ.get("FAKE_PI_PRETOOL_STDERR", "0") == "1":
            print("PreToolUse:Bash says:", file=sys.stderr, flush=True)
        print("fake stream stderr", file=sys.stderr, flush=True)
    else:
        print("fake stdout")
        print("fake stderr", file=sys.stderr)

    sleep_after_output = float(os.environ.get("FAKE_PI_SLEEP_AFTER_OUTPUT", "0"))
    if sleep_after_output:
        time.sleep(sleep_after_output)

    if os.environ.get("FAKE_PI_AUTH_FAILURE", "0") == "1":
        print("No API key found for openai-codex.", file=sys.stderr)
        print("Use /login to log in to a provider via OAuth or API key.", file=sys.stderr)
        return 1

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
    if os.environ.get("FAKE_PI_EXIT_AFTER_ARTIFACTS", "0") != "0":
        return int(os.environ["FAKE_PI_EXIT_AFTER_ARTIFACTS"])
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
    model_args: Sequence[str] | None = None,
    session_dir: str = "tmp/mux/session",
    report_path: str = "tmp/mux/session/build/agent-1.md",
    signal_path: str = "tmp/mux/session/.signals/agent-1.done",
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
    resolved_model_args = list(model_args) if model_args is not None else [
        "--provider",
        "openai-codex",
        "--model",
        "example-model-tier",
        "--thinking",
        "xhigh",
    ]

    command = [
        sys.executable,
        str(PI_BASH),
        "launch",
        session_dir,
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
        report_path,
        "--signal-path",
        signal_path,
        *resolved_model_args,
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
    assert argv[:10] == [
        "--offline",
        "--no-extensions",
        "--tools",
        "read,write,grep,find,ls",
        "--provider",
        "openai-codex",
        "--model",
        "example-model-tier",
        "--thinking",
        "xhigh",
    ]
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
    assert "default pi-bash tool allowlist excludes Bash and Edit" in prompt
    assert "After writing the report, create the success signal by writing this exact text" in prompt
    assert "path: tmp/mux/session/build/agent-1.md\nstatus: success" in prompt
    assert "uv run" not in prompt


def test_pi_bash_uses_project_model_config_when_cli_model_args_are_omitted(tmp_path: Path) -> None:
    """Project pi-bash.yaml supplies explicit provider, model, and thinking flags."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)
    (workspace / "pi-bash.yaml").write_text(
        "default:\n"
        "  provider: openai-codex\n"
        "  model: gpt-5.5\n"
        "  thinking: xhigh\n"
    )

    result = run_pi_bash(workspace=workspace, fake_pi=fake_pi, tmp_path=tmp_path, model_args=())

    assert result.returncode == 0, result.stderr
    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--provider"] == ["openai-codex"]
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--model"] == ["gpt-5.5"]
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--thinking"] == ["xhigh"]
    wrapper_text = log_path(workspace, "wrapper.log").read_text()
    assert "model_config_sources:" in wrapper_text
    assert "pi-bash.yaml" in wrapper_text


def test_pi_bash_normalizes_provider_prefixed_model_arg(tmp_path: Path) -> None:
    """A provider-prefixed --model still becomes explicit provider and model flags."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        model_args=["--model", "openai-codex/gpt-5.5", "--thinking", "xhigh"],
    )

    assert result.returncode == 0, result.stderr
    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--provider"] == ["openai-codex"]
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--model"] == ["gpt-5.5"]


def test_pi_bash_configure_writes_project_model_config(tmp_path: Path) -> None:
    """The configure command persists non-secret pi-bash defaults."""
    workspace = create_workspace(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(PI_BASH),
            "configure",
            "--scope",
            "project",
            "--cwd",
            str(workspace),
            "--provider",
            "openai-codex",
            "--model",
            "gpt-5.5",
            "--thinking",
            "xhigh",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"wrote {workspace / 'pi-bash.yaml'}\n"
    config_text = (workspace / "pi-bash.yaml").read_text()
    assert "provider: openai-codex" in config_text
    assert "model: gpt-5.5" in config_text
    assert "thinking: xhigh" in config_text
    assert "auth:" in config_text


def test_pi_bash_auth_help_prints_oauth_setup(tmp_path: Path) -> None:
    """Auth help gives a separate-terminal setup flow without secrets."""
    workspace = create_workspace(tmp_path)

    result = subprocess.run(
        [sys.executable, str(PI_BASH), "auth-help", "--cwd", str(workspace)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Open a separate terminal" in result.stdout
    assert "pi --provider openai-codex --model gpt-5.5 --thinking xhigh" in result.stdout
    assert "/login" in result.stdout
    assert "ChatGPT Plus/Pro (Codex)" in result.stdout


def test_pi_bash_auth_failure_includes_setup_hint(tmp_path: Path) -> None:
    """Provider auth failures explain how to configure pi before retrying."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        env_overrides={"FAKE_PI_WRITE_ARTIFACTS": "0", "FAKE_PI_AUTH_FAILURE": "1"},
    )

    assert result.returncode != 0
    assert "pi-bash authentication/setup required" in result.stderr
    assert "pi --provider openai-codex --model example-model-tier --thinking xhigh" in result.stderr
    assert "ChatGPT Plus/Pro (Codex)" in result.stderr


def test_pi_bash_stream_tees_events_to_logs_and_wrapper_stderr(tmp_path: Path) -> None:
    """Streaming workers preserve stdout protocol while exposing child JSONL live on stderr."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(workspace=workspace, fake_pi=fake_pi, tmp_path=tmp_path, extra_args=["--stream"])

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert '"type":"agent_start"' in result.stderr
    assert '"type":"tool_execution_start"' in result.stderr
    assert "pi> fake stream stderr" in result.stderr

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
    assert argv[:6] == ["--offline", "--mode", "json", "--no-extensions", "--tools", "read,write,grep,find,ls"]
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--provider"] == ["openai-codex"]


def test_pi_bash_stream_allows_startup_network_opt_out(tmp_path: Path) -> None:
    """Explicit startup-network opt-out omits the default pi --offline flag."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream", "--allow-startup-network"],
    )

    assert result.returncode == 0, result.stderr
    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert "--offline" not in argv
    assert argv[:5] == ["--mode", "json", "--no-extensions", "--tools", "read,write,grep,find,ls"]


def test_pi_bash_stream_defaults_to_bounded_startup_and_idle_timeouts(tmp_path: Path) -> None:
    """Streaming workers fail closed by default on startup and later output stalls."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(workspace=workspace, fake_pi=fake_pi, tmp_path=tmp_path, extra_args=["--stream"])

    assert result.returncode == 0, result.stderr
    wrapper_text = log_path(workspace, "wrapper.log").read_text()
    assert "startup_timeout_seconds: 60" in wrapper_text
    assert "idle_timeout_seconds: 600" in wrapper_text
    assert "offline: True" in wrapper_text


def test_pi_bash_stream_prefixes_child_hook_stderr(tmp_path: Path) -> None:
    """Mirrored child hook output is attributable to the inner pi worker."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream"],
        env_overrides={"FAKE_PI_PRETOOL_STDERR": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "pi> PreToolUse:Bash says:" in result.stderr
    stderr_text = log_path(workspace, "stderr.log").read_text()
    assert "PreToolUse:Bash says:" in stderr_text
    assert "pi> PreToolUse:Bash says:" not in stderr_text


def test_pi_bash_stream_no_mirror_preserves_logs(tmp_path: Path) -> None:
    """No-mirror mode suppresses live child output while keeping logs and events."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream", "--no-mirror"],
    )

    assert result.returncode == 0, result.stderr
    assert '"type":"agent_start"' not in result.stderr
    assert "fake stream stderr" not in result.stderr
    assert '"type":"agent_start"' in log_path(workspace, "events.jsonl").read_text()
    assert "fake stream stderr\n" in log_path(workspace, "stderr.log").read_text()


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


def test_pi_bash_stream_startup_timeout_terminates_silent_child_and_updates_manifest(tmp_path: Path) -> None:
    """Streaming workers fail fast when no first child output arrives."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=[
            "--stream",
            "--startup-warn-after",
            "0",
            "--startup-timeout",
            "0.1",
            "--idle-timeout",
            "5",
            "--shutdown-timeout",
            "0.1",
        ],
        env_overrides={"FAKE_PI_SLEEP_BEFORE_OUTPUT": "5"},
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "startup timeout reached; terminating child process group" in result.stderr
    assert "wrapper lifecycle error: pi produced no startup output for 0.1s" in result.stderr

    latest = json.loads((workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.latest.json").read_text())
    assert latest["status"] == "failed"
    assert latest["child_pid"]
    assert "startup output" in latest["error"]


def test_pi_bash_stream_idle_timeout_terminates_silent_child_and_updates_manifest(tmp_path: Path) -> None:
    """Streaming workers terminate post-startup stalled children and persist terminal manifest state."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream", "--startup-warn-after", "0", "--idle-timeout", "0.1", "--shutdown-timeout", "0.1"],
        env_overrides={"FAKE_PI_SLEEP_AFTER_OUTPUT": "5"},
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "idle timeout reached; terminating child process group" in result.stderr
    assert "wrapper lifecycle error: pi produced no child output for 0.1s" in result.stderr

    latest = json.loads((workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.latest.json").read_text())
    assert latest["status"] == "failed"
    assert latest["child_pid"]
    assert "no child output" in latest["error"]


def test_pi_bash_stream_warns_without_killing_when_child_delays_first_event(tmp_path: Path) -> None:
    """Streaming workers warn on startup silence without killing a healthy child."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        extra_args=["--stream", "--startup-warn-after", "0.1", "--shutdown-timeout", "0.1"],
        env_overrides={"FAKE_PI_SLEEP_BEFORE_OUTPUT": "0.2"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert "no child stdout/stderr after 0.1s in stream mode" in result.stderr
    assert "continuing until startup timeout" in result.stderr
    assert "process_tree:" in result.stderr
    assert '"type":"agent_start"' in log_path(workspace, "events.jsonl").read_text()
    wrapper_text = log_path(workspace, "wrapper.log").read_text()
    assert "child_pid:" in wrapper_text
    assert "command:" in wrapper_text
    assert "<redacted>" in wrapper_text
    assert "Write the report and signal files." not in wrapper_text


def test_pi_bash_nonzero_child_with_valid_protocol_succeeds(tmp_path: Path) -> None:
    """A valid report and success signal are authoritative over child exit code."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        env_overrides={"FAKE_PI_EXIT_AFTER_ARTIFACTS": "3"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0"
    assert "protocol valid; treating child issue as success" in log_path(workspace, "stderr.log").read_text()
    assert "child_exit_code=3" in log_path(workspace, "wrapper.log").read_text()


def test_pi_bash_clears_stale_protocol_artifacts_before_launch(tmp_path: Path) -> None:
    """Stale report and signal files cannot satisfy a later launch."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)
    report_path = workspace / "tmp" / "mux" / "session" / "build" / "agent-1.md"
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
    signal_path.write_text("path: tmp/mux/session/build/agent-1.md\nstatus: success\n")

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        env_overrides={"FAKE_PI_WRITE_ARTIFACTS": "0"},
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "missing report file" in result.stderr
    assert not report_path.exists()
    assert not signal_path.exists()


def test_pi_bash_accepts_absolute_protocol_paths_inside_session(tmp_path: Path) -> None:
    """Absolute session/report/signal paths are allowed only when contained by cwd/session."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)
    session_dir = workspace / "tmp" / "mux" / "session"
    report_path = session_dir / "build" / "agent-1.md"
    signal_path = session_dir / ".signals" / "agent-1.done"

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        session_dir=str(session_dir),
        report_path=str(report_path),
        signal_path=str(signal_path),
    )

    assert result.returncode == 0, result.stderr
    assert report_path.exists()
    assert signal_path.exists()


def test_pi_bash_rejects_session_dir_outside_cwd_before_launch(tmp_path: Path) -> None:
    """Session logs are never placed outside cwd."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)
    outside_session = tmp_path / "outside-session"

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        session_dir=str(outside_session),
        report_path=str(outside_session / "build" / "agent-1.md"),
        signal_path=str(outside_session / ".signals" / "agent-1.done"),
    )

    assert result.returncode != 0
    assert "session_dir must resolve inside cwd" in result.stderr
    assert not (tmp_path / "fake" / "argv.json").exists()


def test_pi_bash_rejects_protocol_paths_outside_session_before_cleanup(tmp_path: Path) -> None:
    """Stale artifact cleanup cannot unlink paths outside the declared session."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)
    victim = workspace / "reports" / "agent-1.md"
    victim.parent.mkdir()
    victim.write_text("do not delete")

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        report_path="reports/agent-1.md",
    )

    assert result.returncode != 0
    assert "report_path must resolve inside session_dir" in result.stderr
    assert victim.read_text() == "do not delete"
    assert not (tmp_path / "fake" / "argv.json").exists()


def test_pi_bash_rejects_absolute_protocol_path_outside_cwd_before_cleanup(tmp_path: Path) -> None:
    """Absolute artifact paths outside cwd are rejected before stale cleanup."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)
    victim = tmp_path / "outside-report.md"
    victim.write_text("do not delete")

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        report_path=str(victim),
    )

    assert result.returncode != 0
    assert "report_path must resolve inside cwd" in result.stderr
    assert victim.read_text() == "do not delete"
    assert not (tmp_path / "fake" / "argv.json").exists()


def test_pi_bash_rejects_parent_directory_traversal_before_cleanup(tmp_path: Path) -> None:
    """Parent traversal is rejected even when cleanup would target a file."""
    workspace = create_workspace(tmp_path)
    fake_pi = write_fake_pi(tmp_path)
    victim = tmp_path / "outside-report.md"
    victim.write_text("do not delete")

    result = run_pi_bash(
        workspace=workspace,
        fake_pi=fake_pi,
        tmp_path=tmp_path,
        report_path="../outside-report.md",
    )

    assert result.returncode != 0
    assert "report_path must not contain parent directory traversal" in result.stderr
    assert victim.read_text() == "do not delete"
    assert not (tmp_path / "fake" / "argv.json").exists()


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
