#!/usr/bin/env python3
"""Behavior checks for pimux parent delivery and recovery helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARENT_DELIVERY_RUNTIME = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "parent-delivery.ts"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);
const writeJson = (value) => process.stdout.write(JSON.stringify(value ?? null));

if (payload.action === "flush") {
  const queue = new Map(payload.deliveries.map((delivery) => [delivery.key, delivery]));
  const calls = [];
  try {
    const result = await runtime.flushQueuedParentDeliveries({
      queue,
      makeBatchId: () => "batch-1",
      updateTerminalNotificationState: async (deliveries, batchId, phase) => {
        calls.push({ type: "terminal", phase, batchId, keys: deliveries.map((delivery) => delivery.key) });
        if (payload.failQueuedState && phase === "queued") throw new Error("queued state failed");
      },
      sendParentMessage: (batchId, deliveries) => {
        calls.push({ type: "send", batchId, keys: deliveries.map((delivery) => delivery.key) });
        if (payload.failSend) throw new Error("send failed");
      },
      markTerminalDeliveriesSent: (deliveries) => {
        const terminalDeliveryKeys = deliveries.map((delivery) => delivery.terminalDeliveryKey).filter(Boolean);
        if (terminalDeliveryKeys.length > 0) calls.push({ type: "sent-terminal", terminalDeliveryKeys });
      },
      markParentDeliveriesDelivered: async (deliveries) => {
        calls.push({ type: "mark", eventIds: deliveries.flatMap((delivery) => delivery.eventIds) });
        if (payload.failMark) throw new Error("mark failed");
      },
      scheduleRetry: () => calls.push({ type: "retry" }),
    });
    writeJson({ ok: true, result, queueKeys: [...queue.keys()], calls });
  } catch (error) {
    writeJson({ ok: false, error: error instanceof Error ? error.message : String(error), queueKeys: [...queue.keys()], calls });
  }
  process.exit(0);
}

if (payload.action === "terminal_notification") {
  writeJson(runtime.hasDeliveredTerminalNotification(payload.parentState, payload.identity));
  process.exit(0);
}

if (payload.action === "terminal_key") {
  writeJson(runtime.buildTerminalDeliveryKey(payload.input));
  process.exit(0);
}

if (payload.action === "watchdog") {
  writeJson(runtime.shouldNotifyInactivityWatchdog(payload.input));
  process.exit(0);
}

if (payload.action === "ping_gate") {
  writeJson(runtime.shouldSendStatusRequestProbe(payload.activity));
  process.exit(0);
}

throw new Error(`Unsupported action: ${payload.action}`);
""".strip()


def run_runtime(payload: dict[str, Any]) -> Any:
    """Execute the parent-delivery helper through Node and parse JSON output."""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            NODE_RUNTIME_EVAL,
            str(PARENT_DELIVERY_RUNTIME),
            json.dumps(payload),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Node parent-delivery helper execution failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def delivery(
    key: str,
    *,
    event_ids: list[str] | None = None,
    created_at: str = "2026-04-17T10:00:00Z",
    terminal_delivery_key: str | None = None,
    settled_state: str | None = None,
    terminal_event_id: str | None = None,
) -> dict[str, Any]:
    """Build a synthetic queued parent delivery."""
    result: dict[str, Any] = {
        "key": key,
        "bridgeDir": f"/tmp/{key}",
        "launch": {"agentId": f"agent-{key}"},
        "content": f"content {key}",
        "triggerTurn": True,
        "eventIds": event_ids or [f"evt-{key}"],
        "createdAt": created_at,
    }
    if terminal_delivery_key:
        result["terminalDeliveryKey"] = terminal_delivery_key
        result["settledState"] = settled_state or "settled_failure"
        result["terminalEventId"] = terminal_event_id or result["eventIds"][0]
    return result


def test_flush_requeues_deliveries_when_send_fails() -> None:
    """A failed parent send should leave deliveries pending and avoid delivered acknowledgements."""
    result = run_runtime(
        {
            "action": "flush",
            "deliveries": [delivery("b"), delivery("a", created_at="2026-04-17T09:59:00Z")],
            "failSend": True,
        }
    )
    assert result["ok"] is False
    assert result["error"] == "send failed"
    assert set(result["queueKeys"]) == {"a", "b"}
    assert [call["type"] for call in result["calls"]] == ["terminal", "send", "retry"]
    assert not any(call["type"] == "mark" for call in result["calls"])


def test_flush_requeues_deliveries_when_queued_state_persistence_fails() -> None:
    """A failed queued-state write should restore deliveries and schedule retry before send."""
    result = run_runtime(
        {
            "action": "flush",
            "deliveries": [delivery("b"), delivery("a", created_at="2026-04-17T09:59:00Z")],
            "failQueuedState": True,
        }
    )
    assert result["ok"] is False
    assert result["error"] == "queued state failed"
    assert set(result["queueKeys"]) == {"a", "b"}
    assert [call["type"] for call in result["calls"]] == ["terminal", "retry"]
    assert result["calls"][0]["phase"] == "queued"
    assert not any(call["type"] in {"send", "mark"} for call in result["calls"])


def test_flush_marks_delivered_only_after_successful_send() -> None:
    """Delivered IDs should be acknowledged after send succeeds, before terminal delivery metadata is final."""
    result = run_runtime(
        {
            "action": "flush",
            "deliveries": [delivery("b"), delivery("a", event_ids=["evt-a1", "evt-a2"], created_at="2026-04-17T09:59:00Z")],
        }
    )
    assert result["ok"] is True
    assert result["queueKeys"] == []
    assert [call["type"] for call in result["calls"]] == ["terminal", "send", "mark", "terminal"]
    assert result["calls"][0]["phase"] == "queued"
    assert result["calls"][1]["keys"] == ["a", "b"]
    assert result["calls"][2]["eventIds"] == ["evt-a1", "evt-a2", "evt-b"]
    assert result["calls"][3]["phase"] == "delivered"


def test_terminal_notification_identity_prevents_duplicate_delivered_notifications() -> None:
    """Only an already-delivered matching terminal identity should suppress re-notification."""
    parent_state = {
        "terminalNotificationDeliveredAt": "2026-04-17T10:05:00Z",
        "terminalState": "settled_completion",
        "terminalEventId": "evt-closeout",
    }
    identity = {"terminalState": "settled_completion", "terminalEventId": "evt-closeout"}
    assert run_runtime({"action": "terminal_notification", "parentState": parent_state, "identity": identity}) is True
    assert run_runtime(
        {
            "action": "terminal_notification",
            "parentState": parent_state,
            "identity": {"terminalState": "settled_completion", "terminalEventId": "evt-other"},
        }
    ) is False
    assert run_runtime(
        {
            "action": "terminal_notification",
            "parentState": {"terminalState": "settled_completion", "terminalEventId": "evt-closeout"},
            "identity": identity,
        }
    ) is False


def test_terminal_delivery_key_prefers_child_terminal_event_identity() -> None:
    """Stable terminal event ids should dedupe across bridge/report path churn for one child."""
    base = {
        "agentId": "child-a",
        "settledState": "settled_failure",
        "terminalEventId": "evt-terminal",
        "bridgeDir": "/tmp/bridge-a",
        "reportPath": "/tmp/bridge-a/reports/001-failure.md",
    }
    same_terminal = run_runtime(
        {
            "action": "terminal_key",
            "input": {**base, "bridgeDir": "/tmp/removed-bridge", "reportPath": "/tmp/missing.md"},
        }
    )
    assert run_runtime({"action": "terminal_key", "input": base}) == same_terminal
    assert run_runtime({"action": "terminal_key", "input": {**base, "agentId": "child-b"}}) != same_terminal


def test_terminal_notification_identity_can_use_delivery_key_or_delivered_event_id() -> None:
    """Durable terminal keys and delivered event ids should both suppress late duplicates."""
    identity = {
        "terminalDeliveryKey": "terminal:agent=child-a:state=settled_failure:event=evt-terminal",
        "terminalState": "settled_failure",
        "terminalEventId": "evt-terminal",
    }
    assert run_runtime(
        {
            "action": "terminal_notification",
            "parentState": {
                "terminalNotificationDeliveredAt": "2026-04-17T10:05:00Z",
                "terminalDeliveryKey": identity["terminalDeliveryKey"],
            },
            "identity": identity,
        }
    ) is True
    assert run_runtime(
        {
            "action": "terminal_notification",
            "parentState": {
                "deliveredEventIds": ["evt-terminal"],
                "terminalState": "settled_failure",
                "terminalEventId": "evt-terminal",
            },
            "identity": identity,
        }
    ) is True
    assert run_runtime(
        {
            "action": "terminal_notification",
            "parentState": {
                "terminalNotificationDeliveredAt": "2026-04-17T10:05:00Z",
                "terminalDeliveryKey": identity["terminalDeliveryKey"],
            },
            "identity": {
                "terminalDeliveryKey": "terminal:agent=recovery-child:state=settled_completion:event=evt-recovery",
                "terminalState": "settled_completion",
                "terminalEventId": "evt-recovery",
            },
        }
    ) is False


def test_flush_requeues_terminal_delivery_when_send_fails() -> None:
    """Terminal dedupe must not suppress a delivery that was never sent."""
    terminal = delivery(
        "terminal-a",
        terminal_delivery_key="terminal:agent=child-a:state=settled_failure:event=evt-terminal",
        terminal_event_id="evt-terminal",
    )
    result = run_runtime({"action": "flush", "deliveries": [terminal], "failSend": True})
    assert result["ok"] is False
    assert result["queueKeys"] == ["terminal-a"]
    assert [call["type"] for call in result["calls"]] == ["terminal", "send", "retry"]


def test_flush_does_not_requeue_sent_terminal_delivery_when_ack_persistence_fails() -> None:
    """Once parent send succeeds, terminal deliveries should not be resent because ack persistence failed."""
    terminal = delivery(
        "terminal-a",
        terminal_delivery_key="terminal:agent=child-a:state=settled_failure:event=evt-terminal",
        terminal_event_id="evt-terminal",
    )
    result = run_runtime({"action": "flush", "deliveries": [terminal], "failMark": True})
    assert result["ok"] is False
    assert result["queueKeys"] == []
    assert [call["type"] for call in result["calls"]] == ["terminal", "send", "sent-terminal", "mark"]
    assert result["calls"][2]["terminalDeliveryKeys"] == ["terminal:agent=child-a:state=settled_failure:event=evt-terminal"]


def test_watchdog_notifies_once_per_quiet_window() -> None:
    """The inactivity watchdog should suppress duplicate notifications within the same quiet window."""
    base_input = {
        "activity": {"activityState": "running_quiet", "quietForMs": 700_000},
        "lastActivity": "2026-04-17T10:00:00Z",
        "nowMs": 1_776_420_600_000,
        "thresholdMs": 600_000,
    }
    assert run_runtime({"action": "watchdog", "input": base_input}) is True
    assert run_runtime(
        {
            "action": "watchdog",
            "input": {**base_input, "lastNotifiedAt": "2026-04-17T10:05:00Z", "nowMs": 1_776_420_360_000},
        }
    ) is False
    assert run_runtime(
        {
            "action": "watchdog",
            "input": {**base_input, "lastNotifiedAt": "2026-04-17T10:05:00Z", "nowMs": 1_776_421_200_000},
        }
    ) is True
    assert run_runtime(
        {
            "action": "watchdog",
            "input": {**base_input, "activity": {"activityState": "running_recent_activity", "quietForMs": 10_000}},
        }
    ) is False


def test_ping_agent_probe_gate_blocks_settled_and_missing_agents() -> None:
    """Status probes should only be sent to bridge-running agents with a live or inspectable session."""
    assert run_runtime(
        {"action": "ping_gate", "activity": {"bridgeSettlementState": "running", "activityState": "running_quiet"}}
    ) is True
    assert run_runtime(
        {"action": "ping_gate", "activity": {"bridgeSettlementState": "settled_completion", "activityState": "settled"}}
    ) is False
    assert run_runtime(
        {
            "action": "ping_gate",
            "activity": {
                "bridgeSettlementState": "terminal_report_received",
                "activityState": "terminal_report_waiting_for_exit",
            },
        }
    ) is False
    assert run_runtime(
        {
            "action": "ping_gate",
            "activity": {
                "bridgeSettlementState": "terminal_report_exit_timeout",
                "activityState": "terminal_report_exit_timeout",
            },
        }
    ) is False
    assert run_runtime(
        {"action": "ping_gate", "activity": {"bridgeSettlementState": "running", "activityState": "missing_session"}}
    ) is False
    assert run_runtime(
        {"action": "ping_gate", "activity": {"bridgeSettlementState": "running", "activityState": "terminated"}}
    ) is False
