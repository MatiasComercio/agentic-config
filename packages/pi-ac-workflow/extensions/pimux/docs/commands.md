# pimux commands and tool

Package-owned runtime docs for the `pimux` extension command and tool surfaces.

## Command

Use `/pimux` with:

- `spawn`
- `open`
- `list`
- `tree`
- `navigate`
- `status`
- `activity`
- `ping`
- `capture`
- `send`
- `kill`
- `prune`
- `unlock`
- `smoke-nested`

## Tool

Use the `pimux` tool with actions:

- `spawn`
- `open`
- `list`
- `tree`
- `status`
- `activity`
- `ping_agent`
- `capture`
- `send_message`
- `report_parent`
- `kill`
- `prune`

## Minimal spawn

First after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity.

Spawned pimux children always use `notify-and-follow-up`.

```text
/pimux spawn "Scout the repo and report only the relevant files."
```

## Visual spawn

```text
/pimux spawn --open "Act as an orchestrator and keep the session watchable."
```

## Thinking effort

Use `--thinking` to pass Pi's thinking effort flag to spawned children. Valid levels are `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`.

```text
/pimux spawn --model openai-codex/gpt-5.5 --thinking max "Plan the migration and report the risks."
```

The `--model provider/model:thinking` shortcut remains supported by Pi, but `--thinking` is preferred when model identity and effort should stay separate.

## Messaging

Parent -> child:
- `send_message`

Child -> parent:
- `report_parent`

Valid `report_parent` kinds:
- `progress`
- `question`
- `blocker`
- `failure`
- `closeout`

Parent-side interface delivery should also show parent -> child bridge messages as concise pimux events without triggering an extra turn. Use `send_message` for child-requested answers or user-directed instructions, not hurry-up nudges.

After a terminal `report_parent`, pimux first records `terminal_report_received`, finalizes the managed session, then reports a settled state only after exit evidence exists. If exit evidence does not arrive before timeout, status/activity surface `terminal_report_exit_timeout` with recovery guidance. Terminal settlement notifications remain retryable until the parent delivery queue records delivery, then the terminal identity is idempotently suppressed on later scans. Prune and bridge-directory cleanup drop stale queued terminal deliveries rather than routing them to the parent again.

If a new `spawn` is attempted while terminal settlement verification is pending, pimux fails closed with an explicit `Spawn suppressed` result that names the pending related child instead of creating an ambiguous second child.

## Inspection

- `list` for current-session agents by default
- `tree` for hierarchy shape
- `status` for one agent plus settlement state and pane tail
- `activity` for deterministic no-capture state (`running_recent_activity`, `running_quiet`, `terminal_report_waiting_for_exit`, `terminal_report_exit_timeout`, `settled`, `missing_session`, `terminated`, or `protocol_violation`)
- `ping_agent` / `ping` to send a correlated neutral `status_request`; the child must respond with `progress` if still working or a terminal report only when quality-gated done, blocked, or failed
- `capture` for pane text
- `open` to inspect live in iTerm
- `navigate` to select a node from the current-session hierarchy and act on it
- list/tree/navigation labels keep the agent ID visible while adding role/goal context for easier selection
- hierarchy output should use clearer tree connectors and plain-text badges, with best-effort safe styling when the host interface supports it
- interactive `open`, `capture`, `send`, and `kill` pickers should prefer live agents when no target is provided
- `prune --dry-run` to preview historical cleanup candidates

Auto-prune removes `terminated` or `missing` pimux registry entries aged at least `1d`; pending terminal-report states are retained for recovery. Manual or auto prune also invalidates parent-delivery queue entries and bridge watchers for pruned agents, so stale terminal events from removed bridges are not re-emitted.

## Control-plane recovery

```text
/pimux unlock
```

Releases the fail-closed mux-family parent control-plane lock and restores the pre-lock tool surface for the current session.

## Canned smoke guide

```text
/pimux smoke-nested
```

Writes a deterministic nested smoke-test guide under `tmp/pimux/` with stable ID patterns and the simplified scaffold flow used for routing and settlement checks.
