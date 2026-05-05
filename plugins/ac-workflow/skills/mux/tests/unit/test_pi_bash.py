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


FAKE_PI = r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
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
    assert result.stderr == ""

    stdout_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.stdout.log"
    stderr_log = workspace / "tmp" / "mux" / "session" / "logs" / "agent-1.stderr.log"
    assert stdout_log.read_text() == "fake stdout\n"
    assert stderr_log.read_text() == "fake stderr\n"

    argv = json.loads((tmp_path / "fake" / "argv.json").read_text())
    assert argv[:4] == ["--model", "example/model-tier", "--thinking", "xhigh"]
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
