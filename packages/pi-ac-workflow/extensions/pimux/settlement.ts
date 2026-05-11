export type NotificationMode = "notify-and-follow-up";
export type BridgeEventDirection = "system" | "parent_to_child" | "child_to_parent";
export type BridgeEventType =
	| "launched"
	| "instruction"
	| "answer"
	| "clarification"
	| "status_request"
	| "progress"
	| "question"
	| "blocker"
	| "failure"
	| "closeout"
	| "exited"
	| "shutdown_request";
export type PendingTerminalReportState = "terminal_report_received" | "terminal_report_exit_timeout";
export type SettledTerminalState =
	| "settled_completion"
	| "settled_failure"
	| "settled_blocked"
	| "settled_waiting_on_parent"
	| "protocol_violation";
export type BridgeSettlementState = "running" | PendingTerminalReportState | SettledTerminalState;

export const DEFAULT_TERMINAL_REPORT_EXIT_TIMEOUT_MS = 15_000;

export interface BridgeSettlementEvent {
	eventId: string;
	direction: BridgeEventDirection;
	type: BridgeEventType;
	timestamp?: string;
	requiresResponse?: boolean;
}

export interface BridgeNotificationConfig {
	notificationMode: NotificationMode;
}

export interface BridgeSettlementEvaluation<TEvent extends BridgeSettlementEvent> {
	settledState: BridgeSettlementState;
	terminalEvent?: TEvent;
	protocolViolationReason?: string;
}

export interface BridgeSettlementEvaluationOptions {
	nowMs?: number;
	terminalExitTimeoutMs?: number;
}

function hasExitEvent<TEvent extends BridgeSettlementEvent>(events: TEvent[]): boolean {
	return events.some((event) => event.direction === "system" && event.type === "exited");
}

export function isTerminalChildReportEvent(event: Pick<BridgeSettlementEvent, "direction" | "type">): boolean {
	return event.direction === "child_to_parent" && (event.type === "closeout" || event.type === "failure" || event.type === "blocker" || event.type === "question");
}

function isTerminalDeclaration(event: BridgeSettlementEvent): boolean {
	return isTerminalChildReportEvent(event);
}

function mapTerminalEvent(event: BridgeSettlementEvent): SettledTerminalState {
	switch (event.type) {
		case "closeout":
			return "settled_completion";
		case "failure":
			return "settled_failure";
		case "blocker":
			return "settled_blocked";
		case "question":
			return "settled_waiting_on_parent";
		default:
			throw new Error(`Unsupported terminal bridge event type: ${event.type}`);
	}
}

export function isSettledTerminalState(state: BridgeSettlementState | undefined): state is SettledTerminalState {
	return state === "settled_completion"
		|| state === "settled_failure"
		|| state === "settled_blocked"
		|| state === "settled_waiting_on_parent"
		|| state === "protocol_violation";
}

export function isPendingTerminalReportState(state: BridgeSettlementState | undefined): state is PendingTerminalReportState {
	return state === "terminal_report_received" || state === "terminal_report_exit_timeout";
}

function pendingTerminalState<TEvent extends BridgeSettlementEvent>(
	terminal: TEvent,
	options: BridgeSettlementEvaluationOptions,
): BridgeSettlementEvaluation<TEvent> {
	const terminalMs = terminal.timestamp ? Date.parse(terminal.timestamp) : Number.NaN;
	if (
		options.terminalExitTimeoutMs !== undefined
		&& options.nowMs !== undefined
		&& Number.isFinite(terminalMs)
		&& options.nowMs - terminalMs >= options.terminalExitTimeoutMs
	) {
		return { settledState: "terminal_report_exit_timeout", terminalEvent: terminal };
	}
	return { settledState: "terminal_report_received", terminalEvent: terminal };
}

export function evaluateBridgeSettlement<TEvent extends BridgeSettlementEvent>(
	events: TEvent[],
	options: BridgeSettlementEvaluationOptions = {},
): BridgeSettlementEvaluation<TEvent> {
	const childReports = events.filter((event) => event.direction === "child_to_parent");
	const closeouts = childReports.filter((event) => event.type === "closeout");
	if (closeouts.length > 1) {
		return {
			settledState: "protocol_violation",
			protocolViolationReason: "Multiple closeout declarations were emitted.",
		};
	}
	if (closeouts.length === 1) {
		const closeout = closeouts[0];
		const index = childReports.findIndex((event) => event.eventId === closeout.eventId);
		const later = index >= 0 ? childReports.slice(index + 1)[0] : undefined;
		if (later) {
			return {
				settledState: "protocol_violation",
				protocolViolationReason: `Post-closeout child report detected: ${later.type} (${later.eventId})`,
			};
		}
		if (!hasExitEvent(events)) return pendingTerminalState(closeout, options);
		return {
			settledState: "settled_completion",
			terminalEvent: closeout,
		};
	}

	const terminal = [...childReports].reverse().find((event) => isTerminalDeclaration(event));
	if (!terminal) {
		if (!hasExitEvent(events)) return { settledState: "running" };
		return {
			settledState: "protocol_violation",
			protocolViolationReason: "Child exited without a valid terminal declaration.",
		};
	}
	if (!hasExitEvent(events)) return pendingTerminalState(terminal, options);
	return {
		settledState: mapTerminalEvent(terminal),
		terminalEvent: terminal,
	};
}

export function shouldDeliverBridgeEventToParent(event: Pick<BridgeSettlementEvent, "direction" | "type">): boolean {
	if (event.direction === "parent_to_child") return true;
	if (event.direction !== "child_to_parent") return false;
	return !isTerminalChildReportEvent(event);
}

export function shouldTriggerTurnForEvent(
	event: Pick<BridgeSettlementEvent, "direction" | "type" | "requiresResponse">,
	_launch: BridgeNotificationConfig,
): boolean {
	if (!shouldDeliverBridgeEventToParent(event)) return false;
	if (event.direction === "parent_to_child") return false;
	if (event.type === "progress") return Boolean(event.requiresResponse);
	if (event.requiresResponse) return true;
	return true;
}

export function shouldTriggerTurnForSettledState(
	_state: SettledTerminalState,
	_launch: BridgeNotificationConfig,
): boolean {
	return true;
}
