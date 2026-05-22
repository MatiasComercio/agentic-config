#!/usr/bin/env python3
"""Unit tests for the disabled cc-bash compatibility stub."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[6]
CC_BASH = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux" / "tools" / "cc-bash.py"


def test_cc_bash_launch_is_disabled_without_touching_artifacts(tmp_path: Path) -> None:
    """Launch exits before command resolution, child execution, or artifact writes."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    report_path = workspace / "tmp" / "mux" / "session" / "reports" / "agent-1.md"
    signal_path = workspace / "tmp" / "mux" / "session" / ".signals" / "agent-1.done"

    result = subprocess.run(
        [
            sys.executable,
            str(CC_BASH),
            "launch",
            "tmp/mux/session",
            "agent-1",
            "--role",
            "reviewer",
            "--objective",
            "review bounded change",
            "--scope",
            "workspace only",
            "--task",
            "write report",
            "--report-path",
            str(report_path.relative_to(workspace)),
            "--signal-path",
            str(signal_path.relative_to(workspace)),
            "--model",
            "opus",
            "--cwd",
            str(workspace),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "cc-bash.py is disabled" in result.stderr
    assert "Anthropic disabled subscription access to `claude -p`" in result.stderr
    assert "pi-bash.py or native pimux workers" in result.stderr
    assert not report_path.exists()
    assert not signal_path.exists()


def test_cc_bash_help_remains_available() -> None:
    """The retained stub still exposes help for compatibility/debugging."""
    result = subprocess.run(
        [sys.executable, str(CC_BASH), "launch", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--role" in result.stdout
    assert "--report-path" in result.stdout
