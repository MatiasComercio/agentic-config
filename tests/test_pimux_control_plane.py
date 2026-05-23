#!/usr/bin/env python3
"""Behavior checks for pimux control-plane lock helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTROL_PLANE_RUNTIME = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "control-plane.ts"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);
const writeJson = (value) => process.stdout.write(JSON.stringify(value ?? null));

if (payload.action === "parse") {
  writeJson(runtime.parseExplicitControlPlaneTrigger(payload.text));
  process.exit(0);
}

if (payload.action === "extract_spec_path") {
  writeJson(runtime.extractSpecPathFromUserInput(payload.text));
  process.exit(0);
}

if (payload.action === "resolve_pending_spec_path") {
  writeJson(runtime.resolvePendingControlPlaneSpecPath(payload.lock, payload.text));
  process.exit(0);
}

if (payload.action === "prepare_spawn") {
  writeJson(await runtime.prepareControlPlaneSpawn(payload.lock, payload.prompt));
  process.exit(0);
}

if (payload.action === "build_lock") {
  writeJson(runtime.buildControlPlaneLock(payload.trigger, payload.previousActiveTools));
  process.exit(0);
}

if (payload.action === "evaluate") {
  writeJson(runtime.evaluateControlPlaneToolCall(payload.lock, payload.event, payload.now, payload.context));
  process.exit(0);
}

if (payload.action === "update_tool_result") {
  writeJson(runtime.updateControlPlaneLockForToolResult(payload.lock, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "child_activity") {
  writeJson(runtime.updateControlPlaneLockForChildActivity(payload.lock, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "terminal_settlement") {
  writeJson(runtime.updateControlPlaneLockForTerminalSettlement(payload.lock, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "build_no_polling_supervision") {
  writeJson(runtime.buildNoPollingSupervisionForSpawn(payload.agentId, payload.now));
  process.exit(0);
}

if (payload.action === "evaluate_no_polling_supervision") {
  writeJson(runtime.evaluateNoPollingSupervisionToolCall(payload.supervision, payload.event, payload.now, payload.context));
  process.exit(0);
}

if (payload.action === "no_polling_tool_result") {
  writeJson(runtime.updateNoPollingSupervisionForToolResult(payload.supervision, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "no_polling_child_activity") {
  writeJson(runtime.updateNoPollingSupervisionForChildActivity(payload.supervision, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "no_polling_terminal_settlement") {
  writeJson(runtime.updateNoPollingSupervisionForTerminalSettlement(payload.supervision, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "is_explicit_live_inspection") {
  writeJson(runtime.isExplicitLiveInspectionRequest(payload.text));
  process.exit(0);
}

if (payload.action === "is_explicit_child_instruction") {
  writeJson(runtime.isExplicitChildInstructionRequest(payload.text));
  process.exit(0);
}

throw new Error(`Unsupported action: ${payload.action}`);
""".strip()


def run_runtime(payload: dict[str, Any], cwd: Path = PROJECT_ROOT) -> Any:
    """Execute the control-plane helper through Node and parse JSON output."""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            NODE_RUNTIME_EVAL,
            str(CONTROL_PLANE_RUNTIME),
            json.dumps(payload),
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Node control-plane helper execution failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def create_branch_spec_workspace(tmp_path: Path, branch_name: str = "pi-adoption-it001") -> Path:
    """Create an isolated git workspace with existing branch-local spec history."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    init_result = subprocess.run(
        ["git", "init"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    checkout_result = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checkout_result.returncode == 0, checkout_result.stdout + checkout_result.stderr

    spec_dir = workspace / ".specs" / "specs" / "2026" / "04" / branch_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "007-existing-spec.md").write_text("# Existing spec\n")
    return workspace


def no_polling_supervision(spawned_at: str = "2026-04-17T10:00:00Z") -> dict[str, Any]:
    """Create a generic post-spawn no-polling supervision state."""
    return run_runtime(
        {
            "action": "build_no_polling_supervision",
            "agentId": "pimux-worker-001",
            "now": spawned_at,
        }
    )


def settled_no_polling_supervision() -> dict[str, Any]:
    """Create no-polling supervision with terminal settlement verification pending."""
    return run_runtime(
        {
            "action": "no_polling_terminal_settlement",
            "supervision": no_polling_supervision(),
            "event": {
                "agentId": "pimux-worker-001",
                "eventId": "evt-closeout-1",
                "timestamp": "2026-04-17T10:03:00Z",
            },
        }
    )


def spawn_post_lock(spawned_at: str = "2026-04-17T10:00:00Z") -> dict[str, Any]:
    """Create a post-spawn mux-ospec lock at a fixed timestamp for pacing tests."""
    pre_spawn = run_runtime(
        {
            "action": "build_lock",
            "trigger": {
                "mode": "mux-ospec",
                "source": "skill-command",
                "specPath": ".specs/specs/2026/04/pi-adoption-it001/007-consolidate-mux-naming-and-enforce-ospec-workflow.md",
                "requiresSpecPath": False,
            },
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        }
    )
    return run_runtime(
        {
            "action": "update_tool_result",
            "lock": pre_spawn,
            "event": {
                "toolName": "pimux",
                "details": {"action": "spawn", "agent": {"agentId": "mux-ospec-stage-001"}},
                "isError": False,
            },
            "now": spawned_at,
        }
    )


def test_parse_skill_command_extracts_mux_ospec_path() -> None:
    """Explicit skill command invocations should bind mux-ospec and capture the path."""
    parsed = run_runtime(
        {
            "action": "parse",
            "text": "/skill:mux-ospec full .specs/specs/2026/04/pi-adoption-it001/007-consolidate-mux-naming-and-enforce-ospec-workflow.md",
        }
    )
    assert parsed == {
        "mode": "mux-ospec",
        "source": "skill-command",
        "specPath": ".specs/specs/2026/04/pi-adoption-it001/007-consolidate-mux-naming-and-enforce-ospec-workflow.md",
        "requiresSpecPath": False,
    }


def test_parse_embedded_skill_trigger_auto_derives_spec_path_from_inline_prompt(tmp_path: Path) -> None:
    """Embedded mux-ospec prompts should derive the next branch-local spec path without AskUserQuestion."""
    workspace = create_branch_spec_workspace(tmp_path)
    parsed = run_runtime(
        {
            "action": "parse",
            "text": (
                '<skill name="mux-ospec" location="/tmp/mux-ospec/SKILL.md">'
                "Use tmux-backed spec stage orchestration."
                "</skill>\n\nfull\nInline prompt auto spec paths for mux ospec and mux roadmap"
            ),
        },
        cwd=workspace,
    )
    assert parsed == {
        "mode": "mux-ospec",
        "source": "embedded-skill",
        "specPath": ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-ospec-and-mux-roadmap.md",
        "requiresSpecPath": False,
    }


def test_parse_mux_roadmap_inline_prompt_auto_derives_spec_path(tmp_path: Path) -> None:
    """Explicit mux-roadmap prompts should also mirror the current-branch spec-path pattern."""
    workspace = create_branch_spec_workspace(tmp_path)
    parsed = run_runtime(
        {
            "action": "parse",
            "text": "/mux-roadmap Inline prompt auto spec paths for mux roadmap",
        },
        cwd=workspace,
    )
    assert parsed == {
        "mode": "mux-roadmap",
        "source": "alias-command",
        "specPath": ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-roadmap.md",
        "requiresSpecPath": False,
    }


def test_extract_spec_path_from_follow_up_answer_finds_path_token() -> None:
    """A later user answer should be enough to resolve the pending mux-ospec path."""
    path_text = "Use this spec: .specs/specs/2026/04/pi-adoption-it001/006-make-pimux-the-pi-mux-runtime.md"
    extracted = run_runtime({"action": "extract_spec_path", "text": path_text})
    assert extracted == ".specs/specs/2026/04/pi-adoption-it001/006-make-pimux-the-pi-mux-runtime.md"


def test_pending_mux_ospec_lock_accepts_follow_up_inline_prompt(tmp_path: Path) -> None:
    """A pending mux-ospec lock should resolve from a later inline prompt, not only from an explicit path token."""
    workspace = create_branch_spec_workspace(tmp_path)
    pending_lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "embedded-skill", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    resolved_spec_path = run_runtime(
        {
            "action": "resolve_pending_spec_path",
            "lock": pending_lock,
            "text": "full Inline prompt auto spec paths for mux ospec and mux roadmap",
        },
        cwd=workspace,
    )
    assert resolved_spec_path == ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-ospec-and-mux-roadmap.md"


def test_pending_mux_ospec_lock_rejects_help_slash_command(tmp_path: Path) -> None:
    """A pending mux-ospec lock must ignore slash commands like /help when resolving spec paths."""
    workspace = create_branch_spec_workspace(tmp_path)
    pending_lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "embedded-skill", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    resolved_spec_path = run_runtime(
        {
            "action": "resolve_pending_spec_path",
            "lock": pending_lock,
            "text": "/help",
        },
        cwd=workspace,
    )
    assert resolved_spec_path is None

    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": pending_lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the next stage."}},
        }
    )
    assert decision == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.",
    }


def test_pending_mux_ospec_lock_rejects_spec_slash_command(tmp_path: Path) -> None:
    """A pending mux-ospec lock must ignore slash commands like /spec CREATE when resolving spec paths."""
    workspace = create_branch_spec_workspace(tmp_path)
    pending_lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "embedded-skill", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    resolved_spec_path = run_runtime(
        {
            "action": "resolve_pending_spec_path",
            "lock": pending_lock,
            "text": "/spec CREATE",
        },
        cwd=workspace,
    )
    assert resolved_spec_path is None

    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": pending_lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the next stage."}},
        }
    )
    assert decision == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.",
    }


def test_pending_mux_roadmap_lock_accepts_follow_up_inline_prompt(tmp_path: Path) -> None:
    """A pending mux-roadmap lock should also resolve from a later inline prompt."""
    workspace = create_branch_spec_workspace(tmp_path)
    pending_lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-roadmap", "source": "alias-command", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    resolved_spec_path = run_runtime(
        {
            "action": "resolve_pending_spec_path",
            "lock": pending_lock,
            "text": "Inline prompt auto spec paths for mux roadmap",
        },
        cwd=workspace,
    )
    assert resolved_spec_path == ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-roadmap.md"



def test_prepare_spawn_creates_missing_bound_spec_and_binds_prompt(tmp_path: Path) -> None:
    """Bound mux spec paths should be created before spawn and injected into the child prompt when absent."""
    workspace = create_branch_spec_workspace(tmp_path)
    spec_path = ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-ospec-and-mux-roadmap.md"
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {
                "mode": "mux-ospec",
                "source": "skill-command",
                "specPath": spec_path,
                "requiresSpecPath": False,
            },
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    prepared = run_runtime(
        {
            "action": "prepare_spawn",
            "lock": lock,
            "prompt": "Run the next stage.",
        },
        cwd=workspace,
    )
    assert prepared == {
        "prompt": f"Use this spec path for the run, and create it first if missing:\n{spec_path}\n\nRun the next stage.",
        "specPath": spec_path,
        "specCreated": True,
    }
    created_spec = workspace / spec_path
    assert created_spec.exists()
    created_text = created_spec.read_text()
    assert created_text.startswith("# Human Section\n")
    assert "auto-created by the pimux control-plane runtime" in created_text


def test_pre_spawn_lock_blocks_parent_repo_tools_and_non_spawn_pimux_actions() -> None:
    """Before the first child exists, the parent should be fail-closed to spawn-only orchestration."""
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "skill-command", "requiresSpecPath": False},
            "previousActiveTools": ["read", "bash", "pimux", "AskUserQuestion", "say"],
        }
    )

    blocked_bash = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "bash", "input": {"command": "rg -n pimux ."}},
        }
    )
    assert blocked_bash == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Only pimux, AskUserQuestion, and say are allowed in the parent while the wrapper lock is active.",
    }

    blocked_status = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "last"}},
        }
    )
    assert blocked_status == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Before the first child exists, the only allowed pimux action is spawn.",
    }

    allowed_question = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "AskUserQuestion", "input": {"question": "Which spec path?"}},
        }
    )
    assert allowed_question == {"allow": True}


def test_mux_ospec_inline_prompt_allows_spawn_without_ask_user_question(tmp_path: Path) -> None:
    """Inline mux-ospec prompts should no longer fail closed on missing explicit paths."""
    workspace = create_branch_spec_workspace(tmp_path)
    trigger = run_runtime(
        {
            "action": "parse",
            "text": "/mux-ospec full Inline prompt auto spec paths for mux ospec and mux roadmap",
        },
        cwd=workspace,
    )
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": trigger,
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the next stage."}},
        },
        cwd=workspace,
    )
    assert decision == {"allow": True}


def test_mux_ospec_spawn_is_blocked_only_when_no_path_or_inline_prompt_exists() -> None:
    """Missing mux-ospec input should still fail closed before spawn."""
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "embedded-skill", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        }
    )
    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the next stage."}},
        }
    )
    assert decision == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.",
    }


def test_mux_roadmap_inline_prompt_allows_spawn_without_ask_user_question(tmp_path: Path) -> None:
    """Inline mux-roadmap prompts should derive a branch-local spec path and allow spawn."""
    workspace = create_branch_spec_workspace(tmp_path)
    trigger = run_runtime(
        {
            "action": "parse",
            "text": "/mux-roadmap Inline prompt auto spec paths for mux roadmap",
        },
        cwd=workspace,
    )
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": trigger,
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the roadmap phase."}},
        },
        cwd=workspace,
    )
    assert decision == {"allow": True}


def test_mux_roadmap_spawn_is_blocked_only_when_no_path_or_inline_prompt_exists() -> None:
    """Missing mux-roadmap input should also fail closed before spawn."""
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-roadmap", "source": "alias-command", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        }
    )
    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the roadmap phase."}},
        }
    )
    assert decision == {
        "allow": False,
        "reason": "Explicit mux-roadmap parent is control-plane locked. Explicit mux-roadmap requires an explicit roadmap/spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.",
    }


def test_successful_spawn_transitions_lock_to_post_spawn_supervision() -> None:
    """A successful spawn should enter notify-first post-spawn supervision without permitting repo work."""
    post_spawn = spawn_post_lock()
    assert post_spawn["phase"] == "post_spawn"
    assert post_spawn["lastSpawnedAgentId"] == "mux-ospec-stage-001"
    assert post_spawn.get("lastChildActivityAt") is None
    assert post_spawn["initialVerificationUsed"] is False
    assert post_spawn["recoveryMessageUsed"] is False
    assert post_spawn["settlementVerificationPending"] is False

    blocked_status = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:00:05Z",
        }
    )
    assert blocked_status == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Do not poll pimux; wait for delivered child activity. status/activity/capture/tree/list/open are recovery-only; open is also allowed when the user explicitly asks to watch live. Other check actions are allowed only after terminal settlement or the 10m inactivity watchdog.",
    }

    blocked_read = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "read", "input": {"path": "README.md"}},
        }
    )
    assert blocked_read == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Only pimux, AskUserQuestion, and say are allowed in the parent while the wrapper lock is active.",
    }


def test_post_spawn_blocks_happy_path_verification_checks_until_watchdog() -> None:
    """The parent should wait for delivered child activity instead of doing immediate checks."""
    post_spawn = spawn_post_lock()
    blocked_status = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert blocked_status == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Do not poll pimux; wait for delivered child activity. status/activity/capture/tree/list/open are recovery-only; open is also allowed when the user explicitly asks to watch live. Other check actions are allowed only after terminal settlement or the 10m inactivity watchdog.",
    }

    watchdog_status = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:11:00Z",
        }
    )
    assert watchdog_status == {"allow": True}



def test_capture_and_open_are_recovery_only_after_spawn() -> None:
    """Check-style actions should be blocked on the happy path, including open."""
    post_spawn = spawn_post_lock()
    for action in ("capture", "open"):
        blocked = run_runtime(
            {
                "action": "evaluate",
                "lock": post_spawn,
                "event": {"toolName": "pimux", "input": {"action": action, "target": "mux-ospec-stage-001"}},
                "now": "2026-04-17T10:01:00Z",
            }
        )
        assert blocked == {
            "allow": False,
            "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Do not poll pimux; wait for delivered child activity. status/activity/capture/tree/list/open are recovery-only; open is also allowed when the user explicitly asks to watch live. Other check actions are allowed only after terminal settlement or the 10m inactivity watchdog.",
        }


def test_explicit_live_inspection_allows_open_but_not_polling_checks_after_spawn() -> None:
    """A user request to watch live should allow open only, not status/capture polling."""
    post_spawn = spawn_post_lock()
    context = {"explicitLiveInspectionRequested": True}
    allowed_open = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "open", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:01:00Z",
            "context": context,
        }
    )
    assert allowed_open == {"allow": True}

    for action in ("status", "capture"):
        blocked = run_runtime(
            {
                "action": "evaluate",
                "lock": post_spawn,
                "event": {"toolName": "pimux", "input": {"action": action, "target": "mux-ospec-stage-001"}},
                "now": "2026-04-17T10:01:00Z",
                "context": context,
            }
        )
        assert blocked["allow"] is False

    blocked_message = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Continue."},
            },
            "now": "2026-04-17T10:01:00Z",
            "context": context,
        }
    )
    assert blocked_message["allow"] is False


def test_explicit_live_inspection_detection_is_conservative() -> None:
    """Live visual inspection intent should require both an open/show verb and a live/tab terminal noun."""
    assert run_runtime({"action": "is_explicit_live_inspection", "text": "open both live in tabs"}) is True
    assert run_runtime({"action": "is_explicit_live_inspection", "text": "show me the live agents"}) is True
    assert run_runtime({"action": "is_explicit_live_inspection", "text": "watch live"}) is True
    assert run_runtime({"action": "is_explicit_live_inspection", "text": "open in tmux tabs"}) is True
    assert run_runtime({"action": "is_explicit_live_inspection", "text": "how are they doing?"}) is False
    assert run_runtime({"action": "is_explicit_live_inspection", "text": "check status"}) is False
    assert run_runtime({"action": "is_explicit_live_inspection", "text": "any update?"}) is False



def test_explicit_child_instruction_detection_includes_followups() -> None:
    """User-directed follow-ups should count as child instructions without allowing vague nudges."""
    assert run_runtime({"action": "is_explicit_child_instruction", "text": "send the child a note"}) is True
    assert run_runtime({"action": "is_explicit_child_instruction", "text": "follow up with the child"}) is True
    assert run_runtime({"action": "is_explicit_child_instruction", "text": "send them this follow-up"}) is True
    assert run_runtime({"action": "is_explicit_child_instruction", "text": "continue"}) is False
    assert run_runtime({"action": "is_explicit_child_instruction", "text": "any update?"}) is False



def test_post_spawn_blocks_recovery_message_before_child_activity() -> None:
    """The parent should not message a child unless the child asks or the user explicitly instructs."""
    post_spawn = spawn_post_lock()
    first_message = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Recover the missing path."},
            },
            "now": "2026-04-17T10:00:05Z",
        }
    )
    assert first_message == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Child did not request input. Wait; do not nudge toward closeout.",
    }

    user_directed_message = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Use the explicit path."},
            },
            "context": {"explicitChildInstructionRequested": True},
            "now": "2026-04-17T10:00:05Z",
        }
    )
    assert user_directed_message == {"allow": True}



def test_child_activity_requires_response_before_parent_message_not_polling_tools() -> None:
    """Ordinary progress should not re-arm messages; requiresResponse progress should allow one answer."""
    post_spawn = spawn_post_lock()
    ordinary_progress = run_runtime(
        {
            "action": "child_activity",
            "lock": post_spawn,
            "event": {
                "agentId": "mux-ospec-stage-001",
                "eventId": "evt-progress-1",
                "timestamp": "2026-04-17T10:02:00Z",
                "requiresResponse": False,
            },
        }
    )
    blocked_status = run_runtime(
        {
            "action": "evaluate",
            "lock": ordinary_progress,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:02:05Z",
        }
    )
    assert blocked_status == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Do not poll pimux; wait for delivered child activity. status/activity/capture/tree/list/open are recovery-only; open is also allowed when the user explicitly asks to watch live. Other check actions are allowed only after terminal settlement or the 10m inactivity watchdog.",
    }

    blocked_nudge = run_runtime(
        {
            "action": "evaluate",
            "lock": ordinary_progress,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Continue."},
            },
            "now": "2026-04-17T10:02:10Z",
        }
    )
    assert blocked_nudge == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Child did not request input. Wait; do not nudge toward closeout.",
    }

    needs_answer = run_runtime(
        {
            "action": "child_activity",
            "lock": ordinary_progress,
            "event": {
                "agentId": "mux-ospec-stage-001",
                "eventId": "evt-progress-2",
                "timestamp": "2026-04-17T10:03:00Z",
                "requiresResponse": True,
            },
        }
    )
    allowed_answer = run_runtime(
        {
            "action": "evaluate",
            "lock": needs_answer,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Use option A."},
            },
            "now": "2026-04-17T10:03:10Z",
        }
    )
    assert allowed_answer == {"allow": True}

    after_answer = run_runtime(
        {
            "action": "update_tool_result",
            "lock": needs_answer,
            "event": {"toolName": "pimux", "details": {"action": "send_message"}, "isError": False},
            "now": "2026-04-17T10:03:10Z",
        }
    )
    blocked_second_answer = run_runtime(
        {
            "action": "evaluate",
            "lock": after_answer,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Again."},
            },
            "now": "2026-04-17T10:03:30Z",
        }
    )
    assert blocked_second_answer == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Child did not request input. Wait; do not nudge toward closeout.",
    }



def test_terminal_settlement_rearms_one_final_status_or_activity_only() -> None:
    """Terminal settlement should allow one final status/activity verification, not capture or nudges."""
    post_spawn = spawn_post_lock()
    settled = run_runtime(
        {
            "action": "terminal_settlement",
            "lock": post_spawn,
            "event": {
                "agentId": "mux-ospec-stage-001",
                "eventId": "evt-closeout-1",
                "timestamp": "2026-04-17T10:03:00Z",
            },
        }
    )
    allowed_status = run_runtime(
        {
            "action": "evaluate",
            "lock": settled,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
        }
    )
    allowed_activity = run_runtime(
        {
            "action": "evaluate",
            "lock": settled,
            "event": {"toolName": "pimux", "input": {"action": "activity", "target": "mux-ospec-stage-001"}},
        }
    )
    assert allowed_status == {"allow": True}
    assert allowed_activity == {"allow": True}

    blocked_capture = run_runtime(
        {
            "action": "evaluate",
            "lock": settled,
            "event": {"toolName": "pimux", "input": {"action": "capture", "target": "mux-ospec-stage-001"}},
        }
    )
    assert blocked_capture == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Terminal settlement is ready. Use one final pimux status or activity check, then stop supervising this child.",
    }

    blocked_message = run_runtime(
        {
            "action": "evaluate",
            "lock": settled,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Any update?"},
            },
        }
    )
    assert blocked_message == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Terminal settlement is ready. Use one final pimux status or activity check, then stop supervising this child.",
    }

    after_final_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": settled,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:03:05Z",
        }
    )
    after_final_activity = run_runtime(
        {
            "action": "update_tool_result",
            "lock": settled,
            "event": {"toolName": "pimux", "details": {"action": "activity"}, "isError": False},
            "now": "2026-04-17T10:03:05Z",
        }
    )
    assert after_final_activity["settlementVerificationPending"] is False
    blocked_second_status = run_runtime(
        {
            "action": "evaluate",
            "lock": after_final_status,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:03:10Z",
        }
    )
    assert blocked_second_status == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Do not poll pimux; wait for delivered child activity. status/activity/capture/tree/list/open are recovery-only; open is also allowed when the user explicitly asks to watch live. Other check actions are allowed only after terminal settlement or the 10m inactivity watchdog.",
    }



def test_inactivity_watchdog_allows_one_follow_up_check_without_restarting_polling() -> None:
    """A real inactivity threshold may reopen one check, but not a new polling loop."""
    post_spawn = spawn_post_lock()
    blocked_early = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:05:00Z",
        }
    )
    assert blocked_early["allow"] is False

    allowed_watchdog = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:11:00Z",
        }
    )
    assert allowed_watchdog == {"allow": True}

    after_watchdog_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:11:00Z",
        }
    )
    blocked_again = run_runtime(
        {
            "action": "evaluate",
            "lock": after_watchdog_status,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:11:30Z",
        }
    )
    assert blocked_again == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Do not poll pimux; wait for delivered child activity. status/activity/capture/tree/list/open are recovery-only; open is also allowed when the user explicitly asks to watch live. Other check actions are allowed only after terminal settlement or the 10m inactivity watchdog.",
    }



def test_inactivity_watchdog_allows_neutral_probe_not_freeform_nudge() -> None:
    """The watchdog should allow neutral ping_agent recovery, not a hurry-up message."""
    post_spawn = spawn_post_lock()
    blocked_early_ping = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "ping_agent", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:05:00Z",
        }
    )
    assert blocked_early_ping == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Use ping_agent only for explicit user-requested liveness checks or after the 10m inactivity watchdog.",
    }

    blocked_watchdog_message = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Still there?"},
            },
            "now": "2026-04-17T10:11:00Z",
        }
    )
    assert blocked_watchdog_message == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Child did not request input. Wait; do not nudge toward closeout.",
    }

    allowed_watchdog_ping = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "ping_agent", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:11:00Z",
        }
    )
    assert allowed_watchdog_ping == {"allow": True}

    explicit_probe = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "ping_agent", "target": "mux-ospec-stage-001"}},
            "context": {"explicitChildProbeRequested": True},
            "now": "2026-04-17T10:05:00Z",
        }
    )
    assert explicit_probe == {"allow": True}


def test_no_polling_supervision_blocks_routine_pimux_inspection_after_spawn() -> None:
    """Generic pimux supervision should block routine inspection during the no-activity window."""
    supervision = no_polling_supervision()
    blocked_status = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": supervision,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "pimux-worker-001"}},
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert blocked_status == {
        "allow": False,
        "reason": "pimux no-polling supervision is active. Do not poll pimux; wait for delivered child activity. status/activity/capture/tree/list/open are recovery-only; open is also allowed when the user explicitly asks to watch live. Other check actions are allowed only after terminal settlement or the 10m inactivity watchdog.",
    }

    allowed_watchdog_status = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": supervision,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "pimux-worker-001"}},
            "now": "2026-04-17T10:11:00Z",
        }
    )
    assert allowed_watchdog_status == {"allow": True}


def test_no_polling_supervision_blocks_nudges_until_child_requests_input() -> None:
    """Generic no-polling supervision should also be quality-first for parent messages."""
    supervision = no_polling_supervision()
    blocked_nudge = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": supervision,
            "event": {"toolName": "pimux", "input": {"action": "send_message", "target": "pimux-worker-001", "message": "Continue."}},
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert blocked_nudge == {
        "allow": False,
        "reason": "pimux no-polling supervision is active. Child did not request input. Wait; do not nudge toward closeout.",
    }

    user_directed_message = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": supervision,
            "event": {"toolName": "pimux", "input": {"action": "send_message", "target": "pimux-worker-001", "message": "Use the explicit path."}},
            "context": {"explicitChildInstructionRequested": True},
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert user_directed_message == {"allow": True}

    needs_answer = run_runtime(
        {
            "action": "no_polling_child_activity",
            "supervision": supervision,
            "event": {
                "agentId": "pimux-worker-001",
                "eventId": "evt-progress-1",
                "timestamp": "2026-04-17T10:02:00Z",
                "requiresResponse": True,
            },
        }
    )
    allowed_answer = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": needs_answer,
            "event": {"toolName": "pimux", "input": {"action": "send_message", "target": "pimux-worker-001", "message": "Use option A."}},
            "now": "2026-04-17T10:02:05Z",
        }
    )
    assert allowed_answer == {"allow": True}



def test_no_polling_supervision_allows_explicit_live_open_but_not_polling_checks() -> None:
    """Generic no-polling supervision should honor explicit live open without allowing polling."""
    supervision = no_polling_supervision()
    context = {"explicitLiveInspectionRequested": True}
    allowed_open = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": supervision,
            "event": {"toolName": "pimux", "input": {"action": "open", "target": "pimux-worker-001"}},
            "now": "2026-04-17T10:01:00Z",
            "context": context,
        }
    )
    assert allowed_open == {"allow": True}

    for action in ("status", "capture"):
        blocked = run_runtime(
            {
                "action": "evaluate_no_polling_supervision",
                "supervision": supervision,
                "event": {"toolName": "pimux", "input": {"action": action, "target": "pimux-worker-001"}},
                "now": "2026-04-17T10:01:00Z",
                "context": context,
            }
        )
        assert blocked["allow"] is False

    blocked_message = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": supervision,
            "event": {"toolName": "pimux", "input": {"action": "send_message", "target": "pimux-worker-001", "message": "Continue."}},
            "now": "2026-04-17T10:01:00Z",
            "context": context,
        }
    )
    assert blocked_message["allow"] is False


def test_no_polling_supervision_blocks_bash_sleep_wait_loops_but_allows_normal_commands() -> None:
    """The generic guard should target supervision waits without blocking normal repository commands."""
    supervision = no_polling_supervision()
    blocked_sleep = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": supervision,
            "event": {"toolName": "Bash", "input": {"command": "while true; do sleep 5; done"}},
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert blocked_sleep == {
        "allow": False,
        "reason": "pimux no-polling supervision is active. Do not use Bash sleep/wait loops for supervision; stop and wait for delivered bridge activity instead.",
    }

    allowed_git = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": supervision,
            "event": {"toolName": "Bash", "input": {"command": "git status --short"}},
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert allowed_git == {"allow": True}


def test_no_polling_supervision_allows_one_final_status_or_activity_after_terminal_settlement() -> None:
    """Terminal settlement should reopen exactly one final status/activity check for verification."""
    settled = settled_no_polling_supervision()
    allowed_status = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": settled,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "pimux-worker-001"}},
        }
    )
    allowed_activity = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": settled,
            "event": {"toolName": "pimux", "input": {"action": "activity", "target": "pimux-worker-001"}},
        }
    )
    assert allowed_status == {"allow": True}
    assert allowed_activity == {"allow": True}

    after_status = run_runtime(
        {
            "action": "no_polling_tool_result",
            "supervision": settled,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:03:05Z",
        }
    )
    after_activity = run_runtime(
        {
            "action": "no_polling_tool_result",
            "supervision": settled,
            "event": {"toolName": "pimux", "details": {"action": "activity"}, "isError": False},
            "now": "2026-04-17T10:03:05Z",
        }
    )
    assert after_status["active"] is False
    assert after_activity["active"] is False
    allowed_after_supervision = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": after_status,
            "event": {"toolName": "Bash", "input": {"command": "git status --short"}},
            "now": "2026-04-17T10:03:10Z",
        }
    )
    assert allowed_after_supervision == {"allow": True}


def test_no_polling_settlement_pending_does_not_pretool_block_spawn() -> None:
    """Spawn must reach the executor so it can return a structured suppressed result."""
    settled = settled_no_polling_supervision()
    decision = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": settled,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "agentId": "pimux-repro-new"}},
            "now": "2026-04-17T10:04:00Z",
        }
    )
    assert decision == {"allow": True}


def test_no_polling_settlement_pending_wrong_target_verification_is_blocked_with_related_id() -> None:
    """Final settlement verification should be scoped to the pending child."""
    settled = settled_no_polling_supervision()
    blocked_activity = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": settled,
            "event": {"toolName": "pimux", "input": {"action": "activity", "target": "pimux-repro-new"}},
            "now": "2026-04-17T10:04:00Z",
        }
    )
    assert blocked_activity["allow"] is False
    assert "pimux-worker-001" in blocked_activity["reason"]
    assert "pimux-repro-new" in blocked_activity["reason"]

    blocked_list = run_runtime(
        {
            "action": "evaluate_no_polling_supervision",
            "supervision": settled,
            "event": {"toolName": "pimux", "input": {"action": "list"}},
            "now": "2026-04-17T10:04:00Z",
        }
    )
    assert blocked_list["allow"] is False
    assert "pimux-worker-001" in blocked_list["reason"]


def test_no_polling_final_verification_clears_only_for_related_agent() -> None:
    """A successful final status/activity result for another agent must not settle this child."""
    settled = settled_no_polling_supervision()
    after_wrong_agent = run_runtime(
        {
            "action": "no_polling_tool_result",
            "supervision": settled,
            "event": {
                "toolName": "pimux",
                "details": {"action": "status", "status": {"record": {"agentId": "pimux-repro-new"}}},
                "isError": False,
            },
            "now": "2026-04-17T10:03:05Z",
        }
    )
    assert after_wrong_agent["active"] is True
    assert after_wrong_agent["settlementVerificationPending"] is True

    after_related_agent = run_runtime(
        {
            "action": "no_polling_tool_result",
            "supervision": settled,
            "event": {
                "toolName": "pimux",
                "details": {"action": "activity", "status": {"record": {"agentId": "pimux-worker-001"}}},
                "isError": False,
            },
            "now": "2026-04-17T10:03:05Z",
        }
    )
    assert after_related_agent["active"] is False
