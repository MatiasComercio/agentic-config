#!/usr/bin/env python3
"""Surface checks for pimux runtime consistency fixes."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIMUX_PACKAGE_DIR = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux"
PIMUX_INDEX = PIMUX_PACKAGE_DIR / "index.ts"
PIMUX_BRIDGE = PIMUX_PACKAGE_DIR / "bridge.ts"
PIMUX_RENDER = PIMUX_PACKAGE_DIR / "render.ts"
PIMUX_REGISTRY = PIMUX_PACKAGE_DIR / "registry.ts"
PIMUX_TMUX = PIMUX_PACKAGE_DIR / "tmux.ts"
PIMUX_SHIM = PROJECT_ROOT / ".pi" / "extensions" / "pimux" / "index.ts"


def test_parent_runtime_auto_finalizes_terminal_child_reports() -> None:
    """The parent runtime should auto-finalize a child after a terminal bridge report."""
    text = PIMUX_INDEX.read_text()
    assert "async function finalizeManagedAgentAfterTerminalReport(" in text
    assert "if (terminalReportForAutoExit && !events.some((event) => event.direction === \"system\" && event.type === \"exited\")) {" in text
    assert "events = await finalizeManagedAgentAfterTerminalReport(launch, ctx);" in text


def test_parent_runtime_batches_and_retries_terminal_delivery() -> None:
    """Terminal closeout notification should go through a durable batched parent queue."""
    index_text = PIMUX_INDEX.read_text()
    bridge_text = PIMUX_BRIDGE.read_text()
    parent_delivery_text = (PIMUX_PACKAGE_DIR / "parent-delivery.ts").read_text()
    assert "interface QueuedParentDelivery" in parent_delivery_text
    assert "const parentDeliveryQueue = new Map<string, QueuedParentDelivery>();" in index_text
    assert "const buildParentDeliveryBatchContent" in index_text
    assert "# pimux reports: ${deliveries.length} updates" in index_text
    assert "terminalNotificationDeliveredAt" in bridge_text
    assert "terminalNotificationAttemptCount" in bridge_text
    assert "!notificationDelivered" in index_text
    assert "key: terminalDeliveryKey" in index_text
    assert "terminalDeliveryKey," in index_text
    assert "const processingParentBridges = new Map<string, ParentBridgeProcessingState>();" in index_text
    assert "existing.rerunRequested = true;" in index_text


def test_parent_delivery_ack_happens_after_successful_send() -> None:
    """Deliverable bridge events should not be durably acknowledged before sendMessage succeeds."""
    index_text = PIMUX_INDEX.read_text()
    bridge_text = PIMUX_BRIDGE.read_text()
    parent_delivery_text = (PIMUX_PACKAGE_DIR / "parent-delivery.ts").read_text()
    deliverable_block = index_text.split("if (shouldDeliverBridgeEventToParent(event)) {", 1)[1].split(
        "} else if (!terminalReport) {",
        1,
    )[0]
    assert "enqueueParentDelivery(" in deliverable_block
    assert "delivered.add(event.eventId)" not in deliverable_block
    assert "await flushQueuedParentDeliveries({" in index_text
    assert "markTerminalDeliveriesSent: rememberDeliveredTerminalDeliveries," in index_text
    assert "markParentDeliveriesDelivered," in index_text
    assert "sendParentMessage:" in index_text
    assert "options.markTerminalDeliveriesSent?.(deliveries);" in parent_delivery_text
    assert "await options.markParentDeliveriesDelivered(deliveries);" in parent_delivery_text
    assert "await options.updateTerminalNotificationState(deliveries, batchId, \"delivered\");" in parent_delivery_text
    assert "const retryableDeliveries = sendCompleted ? deliveries.filter((delivery) => !delivery.terminalDeliveryKey) : deliveries;" in parent_delivery_text
    assert "eventIds.push(...delivery.eventIds);" in index_text
    assert "parentState.deliveredEventIds = [...delivered].slice(-500);" in index_text
    assert "deliveredEventIds: uniqueStrings([...(current.deliveredEventIds ?? []), ...(next.deliveredEventIds ?? [])]).slice(-500)," in bridge_text


def test_runtime_invalidates_stale_terminal_deliveries_after_prune_or_bridge_cleanup() -> None:
    """Pruned/missing bridges should clear queued terminal deliveries instead of re-emitting them."""
    index_text = PIMUX_INDEX.read_text()
    parent_delivery_text = (PIMUX_PACKAGE_DIR / "parent-delivery.ts").read_text()
    bridge_text = PIMUX_BRIDGE.read_text()
    assert "const queuedTerminalDeliveryKeys = new Set<string>();" in index_text
    assert "const deliveredTerminalDeliveryKeys = new Set<string>();" in index_text
    assert "const invalidatedBridgeDirs = new Set<string>();" in index_text
    assert "const invalidatedAgentIds = new Set<string>();" in index_text
    assert "const invalidateParentDeliveriesForBridge = (bridgeDir: string): void => {" in index_text
    assert "watcher?.close();" in index_text
    assert "removeQueuedParentDeliveries((delivery) => delivery.bridgeDir === bridgeDir);" in index_text
    assert "const invalidateParentDeliveriesForStatuses = (statuses: ResolvedStatus[]): void => {" in index_text
    assert "invalidatedAgentIds.add(status.record.agentId);" in index_text
    assert "if (!(await bridgeRuntimeExists(entry.bridgeDir))) {" in index_text
    assert "invalidateParentDeliveriesForBridge(entry.bridgeDir);" in index_text
    assert "if (terminalReportPath && !(await fileExists(terminalReportPath))) {" in index_text
    assert "buildTerminalDeliveryKey" in parent_delivery_text
    assert "terminalDeliveryKey?: string;" in bridge_text
    assert "terminalAgentId?: string;" in bridge_text
    assert "terminalReportPath?: string;" in bridge_text


def test_activity_and_ping_agent_surface_is_available() -> None:
    """pimux should expose deterministic activity checks and active status probes."""
    index_text = PIMUX_INDEX.read_text()
    schema_text = (PIMUX_PACKAGE_DIR / "schema.ts").read_text()
    settlement_text = (PIMUX_PACKAGE_DIR / "settlement.ts").read_text()
    registry_text = PIMUX_REGISTRY.read_text()
    render_text = PIMUX_RENDER.read_text()
    assert '"activity"' in schema_text
    assert '"ping_agent"' in schema_text
    assert 'case "activity": {' in index_text
    assert "async function resolveManagedAgentStatus(" in index_text
    assert "const status = await resolveManagedAgentStatus(ctx, target);" in index_text
    assert 'case "ping_agent": {' in index_text
    assert 'case "ping": {' in index_text
    assert 'type: "status_request"' in index_text
    assert '| "status_request"' in settlement_text
    assert "buildAgentActivitySnapshot" in registry_text
    assert "formatAgentActivitySnapshot" in registry_text
    assert "pimux status_request response contract" in render_text
    assert 'throw new Error("ping requires target")' not in index_text


def test_runtime_has_inactivity_watchdog_monitor() -> None:
    """The extension should perform background reconciliation and inactivity watchdog notification."""
    text = PIMUX_INDEX.read_text()
    assert "BACKGROUND_MONITOR_INTERVAL_MS" in text
    assert "processInactivityWatchdog" in text
    assert "pimux inactivity watchdog" in text
    assert "ensureBackgroundMonitor(ctx);" in text
    assert "function runBackgroundTask(task: Promise<void>): void" in text
    assert "runBackgroundTask(processBridgeDeliveries(bridgeDir, getSessionKey(ctx), ctx));" in text
    assert "runBackgroundTask(reconcileParentBridgeWatchers(ctx));" in text
    assert "runBackgroundTask(processInactivityWatchdog(ctx));" in text


def test_ui_selectors_render_string_labels_instead_of_objects() -> None:
    """The open/tree pickers should pass display strings to ctx.ui.select."""
    text = PIMUX_INDEX.read_text()
    assert "const choice = await ctx.ui.select(title, items.map((item) => item.label));" in text
    assert "const selected = items.find((item) => item.label === choice);" in text
    assert "const choice = await ctx.ui.select(title, flattened.map((entry) => entry.label));" in text
    assert "const selected = flattened.find((entry) => entry.label === choice);" in text



def test_spawn_identity_seed_uses_role_and_goal_for_clearer_generated_agent_ids() -> None:
    """Generated agent IDs should draw from both role and goal when available."""
    text = PIMUX_INDEX.read_text()
    assert "function buildAgentIdentitySeed(" in text
    assert "buildAgentIdentitySeed(role, goal, prompt)" in text


def test_interactive_agent_actions_prefer_live_targets_and_support_send_selection() -> None:
    """Interactive open/capture/send/kill flows should steer users toward live agents."""
    text = PIMUX_INDEX.read_text()
    assert 'const selected = await chooseAgent(ctx, "Open pimux agent in iTerm", {' in text
    assert 'const selected = await chooseAgent(ctx, "pimux capture", {' in text
    assert 'const selected = await chooseAgent(ctx, "Send message to pimux agent", {' in text
    assert 'const selected = await chooseAgent(ctx, "Kill pimux agent", {' in text
    assert 'requireSession: true' in text
    assert 'message = (await ctx.ui.input(`Send message to ${target}`, "Enter message..."))?.trim() ?? "";' in text



def test_parent_runtime_surfaces_parent_to_child_bridge_messages() -> None:
    """The parent delivery loop should no longer drop outbound bridge messages on the floor."""
    text = PIMUX_INDEX.read_text()
    assert 'if (event.direction !== "child_to_parent") {' not in text
    assert "if (shouldDeliverBridgeEventToParent(event)) {" in text



def test_child_inbox_uses_exact_message_content_and_steering_delivery() -> None:
    """Child delivery should preserve raw payloads and steer queued messages deterministically."""
    index_text = PIMUX_INDEX.read_text()
    render_text = PIMUX_RENDER.read_text()
    assert "const queuedChildInboxEventIds = new Set<string>();" in index_text
    assert 'pi.sendUserMessage(message, { deliverAs: "steer" });' in index_text
    assert 'return event.message?.trim() || event.summary?.trim() || "";' in render_text



def test_kill_runtime_cascades_to_live_descendants_before_parent_termination() -> None:
    """Killing a parent should recursively terminate live descendants first."""
    text = PIMUX_INDEX.read_text()
    assert "function collectDescendantStatuses(" in text
    assert "async function requestManagedAgentShutdown(" in text
    assert "async function terminateManagedAgentRecord(" in text
    assert "terminated because ancestor" in text
    assert 'event.type === "shutdown_request"' in text
    assert "shouldShutdownTerminatedAgent" in text



def test_command_surface_includes_canned_smoke_nested_mode() -> None:
    """The command surface should expose the canned nested smoke guide mode."""
    text = PIMUX_INDEX.read_text()
    assert '"  /pimux unlock"' in text
    assert 'case "unlock": {' in text
    assert '"  /pimux smoke-nested [--prefix ID] [--output PATH]"' in text
    assert 'case "smoke-nested": {' in text
    assert '"## Wrapper exit rules"' in text
    assert '"- use `failure` when a direct child settled `settled_failure` or `protocol_violation`"' in text
    assert '"- do not make the wrapper itself the killed parent in a cascade test; kill a disposable child-parent pair under the wrapper instead"' in text



def test_parent_control_plane_lock_is_extension_enforced() -> None:
    """The authoritative pimux extension should enforce mux-family parent locking at runtime."""
    text = PIMUX_INDEX.read_text()
    bridge_text = PIMUX_BRIDGE.read_text()
    helper_text = (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "control-plane.ts").read_text()
    assert 'pi.on("input", async (event, ctx) => {' in text
    assert 'pi.on("tool_call", async (event, ctx) => {' in text
    assert 'pi.on("tool_result", async (event, ctx) => {' in text
    assert 'CONTROL_PLANE_LOCK_ENTRY_TYPE' in text
    assert 'NO_POLLING_SUPERVISION_ENTRY_TYPE' in text
    assert 'applyControlPlaneToolSurface(pi);' in text
    assert 'parseExplicitControlPlaneTrigger' in text
    assert 'resolvePendingControlPlaneSpecPath' in text
    assert 'prepareControlPlaneSpawn' in text
    assert 'const preparedSpawn = await prepareControlPlaneSpawn(currentLock, request.prompt, cwd);' in text
    assert 'const specPath = resolvePendingControlPlaneSpecPath(currentLock, event.text, ctx.cwd);' in text
    assert 'evaluateControlPlaneToolCall' in text
    assert 'evaluateNoPollingSupervisionToolCall' in text
    assert 'updateControlPlaneLockForChildActivity' in text
    assert 'updateControlPlaneLockForTerminalSettlement' in text
    assert 'updateControlPlaneLockForToolResult' in text
    assert 'updateNoPollingSupervisionForToolResult' in text
    assert 'POST_SPAWN_ALLOWED_ACTIONS' in helper_text
    assert 'CONTROL_PLANE_INACTIVITY_WATCHDOG_MS' in helper_text
    assert 'Do not poll pimux; wait for delivered child activity.' in helper_text
    assert 'Do not use Bash sleep/wait loops for supervision' in helper_text
    assert 'status/activity/capture/tree/list/open are recovery-only' in helper_text
    assert 'Child did not request input. Wait; do not nudge toward closeout.' in helper_text
    assert 'Use ping_agent only for explicit user-requested liveness checks or after the' in helper_text
    assert 'Terminal settlement is ready. Use one final pimux status or activity check, then stop supervising this child.' in helper_text
    assert 'PIMUX HAPPY-PATH DISCIPLINE: this run is notify-first, not poll-first.' in helper_text
    assert 'FIRST: do not poll pimux and do not use Bash sleep/wait loops; wait for delivered child activity.' in helper_text
    assert 'Allowed happy-path sequence: spawn -> wait for child reports -> answer only requiresResponse=true requests or explicit user instructions -> wait for evidence-backed closeout -> final status/activity verification.' in helper_text
    assert 'after terminal settlement, use one final pimux status or activity check before advancing.' in helper_text
    assert 'Progress is non-terminal; question is terminal waiting-on-parent settlement.' in text
    assert 'For same-session child questions that must continue, use report_parent(progress, requiresResponse=true), not question.' in text
    assert 'For same-session parent input that you need before continuing, emit progress with requiresResponse=true.' in bridge_text
    assert 'Quality, accuracy, and prompt/spec fidelity outrank speed.' in bridge_text
    assert 'Do not close out because the parent asks for updates, says continue, or appears to be waiting.' in bridge_text
    assert 'success criteria are checked, validation/evidence are ready to summarize, and known uncertainty/blockers are disclosed.' in bridge_text
    assert 'FIRST: do not poll pimux and do not use Bash sleep/wait loops; wait for delivered child activity.' in bridge_text
    assert 'NO-POLL: do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity.' in text
    assert 'Use this spec path for the run, and create it first if missing:' in helper_text
    assert 'create the bound spec file before spawn if it does not exist yet.' in helper_text
    assert 'Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn.' in helper_text
    assert 'Explicit mux-roadmap requires an explicit roadmap/spec path or inline prompt before pimux spawn.' in helper_text


def test_closeout_guard_suggests_non_success_terminal_reports_for_wrappers() -> None:
    """Supervisors should get actionable guidance when closeout is blocked by non-success child outcomes."""
    index_text = PIMUX_INDEX.read_text()
    registry_text = PIMUX_REGISTRY.read_text()
    assert "suggestSupervisorTerminalReportKind" in registry_text
    assert 'Suggested terminal report: ${suggestedKind}.' in index_text
    assert 'Use report_parent(${suggestedKind}) if these child outcomes are intentional.' in index_text
    assert 'Wait for unsettled children to reach terminal settlement before using report_parent(closeout).' in index_text



def test_launcher_reports_startup_failures_and_exits_instead_of_dropping_to_a_shell() -> None:
    """Managed launchers should synthesize bridge evidence for startup failures and then exit."""
    tmux_text = PIMUX_TMUX.read_text()
    assert 'new URL("./launcher-exit-cli.ts", import.meta.url)' in tmux_text
    assert '"--no-extensions"' in tmux_text
    assert '...params.extensionPaths.flatMap((extensionPath) => ["-e", extensionPath])' in tmux_text
    assert 'PI_EXIT_CMD=(' in tmux_text
    assert 'export PI_TUI_WRITE_LOG="$PI_LOG"' in tmux_text
    assert '2>&1 | tee "$PI_LOG"' not in tmux_text
    assert 'tee "$PI_LOG"' not in tmux_text
    assert 'PIPESTATUS' not in tmux_text
    assert '"\\${PI_CMD[@]}" "$PROMPT" 2> >(tee -a "$PI_LOG" >&2)' in tmux_text
    assert 'status=$?' in tmux_text
    assert '"\\${PI_EXIT_CMD[@]}" --bridge-dir' in tmux_text
    assert 'exit "$status"' in tmux_text
    assert 'exec "${SHELL:-/bin/bash}"' not in tmux_text



def test_spawn_suppresses_dispatch_when_settlement_verification_is_pending() -> None:
    """Spawn should return a structured suppression instead of bypassing pending settlement."""
    text = PIMUX_INDEX.read_text()
    assert "function buildSpawnSuppression(" in text
    assert 'reason: "terminal_settlement_verification_pending"' in text
    assert "requestedAgentId" in text
    assert "relatedAgentId" in text

    command_spawn_case = text.split('case "spawn": {', 1)[1].split('case "open": {', 1)[0]
    assert "const suppression = buildSpawnSuppression(request, noPollingSupervision);" in command_spawn_case
    assert "ctx.ui.notify(suppression.text, \"warning\")" in command_spawn_case
    assert command_spawn_case.index("buildSpawnSuppression") < command_spawn_case.index("spawnManagedAgent")

    tool_spawn_case = text.rsplit('case "spawn": {', 1)[1].split('case "open": {', 1)[0]
    assert "const suppression = buildSpawnSuppression(request, noPollingSupervision);" in tool_spawn_case
    assert "if (suppression) return buildToolResult(suppression.text, suppression.details);" in tool_spawn_case
    assert tool_spawn_case.index("buildSpawnSuppression") < tool_spawn_case.index("spawnManagedAgent")


def test_spawn_forwards_explicit_thinking_effort_to_child_pi() -> None:
    """pimux spawn should expose and forward Pi's standalone --thinking effort flag."""
    index_text = PIMUX_INDEX.read_text()
    schema_text = (PIMUX_PACKAGE_DIR / "schema.ts").read_text()
    tmux_text = PIMUX_TMUX.read_text()
    assert "THINKING_EFFORT_LEVELS" in schema_text
    assert "[--thinking LEVEL]" in index_text
    assert 'thinking: normalizeThinkingEffort(getStringFlag(parsed, "thinking"))' in index_text
    assert "thinking: params.thinking" in index_text
    assert "thinking: launch.thinking" in index_text
    assert '...(params.thinking ? ["--thinking", params.thinking] : [])' in tmux_text



def test_spawn_resolves_strict_runtime_as_an_explicit_child_extension() -> None:
    """Child launches should carry the authoritative pimux extension plus its strict sibling explicitly."""
    text = PIMUX_INDEX.read_text()
    assert "async function resolveChildExtensionPaths(" in text
    assert 'path.resolve(path.dirname(path.dirname(authoritativeExtensionPath)), "strict-mux-runtime", "index.js")' in text
    assert 'const extensionPaths = await resolveChildExtensionPaths(extensionPath);' in text
    assert 'extensionPaths,' in text



def test_project_local_pimux_extension_is_now_a_tool_free_compatibility_shim() -> None:
    """The project-local pimux entrypoint should no longer register a competing runtime tool."""
    text = PIMUX_SHIM.read_text()
    assert "Project-local pimux compatibility shim." in text
    assert "packages/pi-ac-workflow/extensions/pimux/" in text
    assert "archived at:" in text
    assert "Intentionally empty." in text
