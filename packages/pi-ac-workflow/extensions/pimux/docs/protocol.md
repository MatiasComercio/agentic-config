# pimux protocol

Package-owned runtime protocol docs for the `pimux` extension command, tool, bridge, and settlement behavior.

## Messaging model

- FIRST: do not poll pimux and do not use Bash sleep/wait loops; wait for delivered child activity.
- parent -> child: explicit bridge inbox events via `send_message` answers/user-directed instructions or correlated neutral `status_request` probes from `ping_agent`
- child -> parent: explicit bridge reports via `report_parent`
- ordinary child `progress` is notification-only unless `requiresResponse=true`
- one hop only: L2 reports to L1, L1 reports to L0

## Report shape

Closeout reports must be useful from the parent delivery summary alone. The runtime now persists a closeout report artifact even when the child only provides a short summary, and normalizes saved reports so they include:

- `## Table of Contents`
- `## Executive Summary`
- a next-step recommendation for the parent/orchestrator

Children should still provide `reportMarkdown` with evidence whenever possible; normalization is a safety net, not a substitute for good closeout content.

## Authority model

Only the authoritative direct child session for a bridge may call `report_parent`.

Implications:
- helper subagents are local-only
- helper completion is not settlement
- helper misuse of `pimux` / `report_parent` is invalid

## Settlement model

- `progress` is non-terminal
- for a child that must ask the parent and continue in the same session, use `progress` with `requiresResponse=true`
- `question` is terminal waiting-on-parent settlement; do not use it when the child should keep working after the answer
- terminal report without exit -> `terminal_report_received`
- terminal report still alive after timeout -> `terminal_report_exit_timeout`
- `closeout + exit` -> `settled_completion`
- `failure + exit` -> `settled_failure`
- `blocker + exit` -> `settled_blocked`
- `question + exit` -> `settled_waiting_on_parent`
- exit without terminal declaration -> `protocol_violation`

After a terminal child report, the pimux runtime finalizes the managed session promptly instead of leaving the child alive in an ambiguous post-closeout state.
The child should not keep chatting or continue work after emitting a terminal report.
`terminal_report_received` and `terminal_report_exit_timeout` are not settled success states; supervisors must wait for exit evidence or recover explicitly.
Terminal settlement notification is durable parent-delivery work: bursty terminal reports may be batched, and a terminal notification remains retryable until the parent delivery queue records delivery metadata for that bridge. Delivered terminal identities are idempotent: the same child `agentId` + settled state + terminal event id is surfaced to the parent at most once, and prune or bridge cleanup invalidates stale queued terminal deliveries instead of re-emitting them as fresh parent input.

## Nested orchestrator rule

If a child spawns direct pimux children, it must not emit `closeout` until every direct pimux child is `settled_completion`.

When direct child outcomes are intentionally non-success, the supervising wrapper should propagate the matching terminal kind and exit cleanly instead of forcing `closeout` or relying on manual kill:

- `settled_waiting_on_parent` -> `question`
- `settled_blocked` -> `blocker`
- `settled_failure` or `protocol_violation` -> `failure`

For cascade-kill testing, keep the wrapper alive and kill a disposable child parent/descendant pair under it rather than making the wrapper itself the killed parent.

## Explicit skill-trigger rule

When the parent session entered this family through an explicit `pimux`, `mux`, `mux-ospec`, or `mux-roadmap` skill trigger, that trigger is a runtime commitment, not a suggestion.

- The parent must stay control-plane only.
- The parent may rely on wrapper/runtime-provided protocol references, prepare bounded handoff from explicit user input, and spawn or message children.
- The substantive domain work must be carried by the spawned authoritative child session(s).
- Do not replace the requested pimux flow with a direct parent-side answer, analysis, or implementation.
- For explicit mux-family wrappers, the parent is fail-closed to `pimux`, `AskUserQuestion`, and `say` until the user explicitly runs `/pimux unlock`.
- If the chosen wrapper is wrong for the task, say so and stop or switch cleanly; do not silently degrade to a non-pimux workflow.

## Supervision pacing rule

Default parent behavior is asynchronous.

After dispatch, the parent should let the child work instead of busy-waiting with Bash sleep/wait loops, repeated `status` checks, or repeated nudges.

Inspect or intervene only when:
- the child emits a bridge report
- the user asks to inspect live progress
- a real downstream handoff now depends on settlement
- the runtime inactivity watchdog reports that a child exceeded the quiet threshold
- there is concrete evidence of a stall, blocker, or protocol problem

For explicit mux-family wrappers, the notify-first default is stricter:
- child bridge notifications are delivered automatically
- after spawn, do not call `status`, `activity`, `capture`, `tree`, `list`, or `open` on the happy path, except `open` when the user explicitly asks to watch live
- wait for delivered child activity; after a child progress report arrives, use `send_message` only when `requiresResponse=true` or when the user explicitly asks to instruct the child
- treat `status`, `activity`, `capture`, `tree`, `list`, and `open` as recovery-only tools for suspected stall/protocol violation/failure or the inactivity-only watchdog; `open` is also allowed for explicit user live-inspection requests
- use `activity` when deterministic bridge/process state is enough and pane capture is unnecessary
- use `ping_agent` only as a neutral active recovery probe; the child must answer the `status_request` with `progress` if still working or a terminal report only if quality-gated completion/blocker/failure is real
- after terminal settlement, use one final `pimux status` or `pimux activity` check for the pending child before advancing or dispatching another child

Do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity. One targeted `status` / `capture` check at a real recovery decision point is fine. Continuous polling is not. Do not nudge children toward closeout; quality, accuracy, and prompt/spec fidelity outrank speed.

## Session scope rule

Default supervision is scoped to the current session hierarchy. Broaden scope only when explicitly needed.
