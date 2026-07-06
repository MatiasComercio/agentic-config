import type { BridgeLaunchFile } from "./bridge.ts";
import type { AgentActivitySnapshot } from "./registry.ts";
import type { BridgeSettlementState, SettledTerminalState } from "./settlement.ts";

export interface QueuedParentDelivery {
	key: string;
	bridgeDir: string;
	launch: BridgeLaunchFile;
	content: string;
	triggerTurn: boolean;
	eventIds: string[];
	agentId?: string;
	reportPath?: string;
	terminalDeliveryKey?: string;
	terminalEventId?: string;
	settledState?: SettledTerminalState;
	protocolViolationReason?: string;
	createdAt: string;
}

export interface TerminalDeliveryIdentityInput {
	bridgeDir: string;
	agentId?: string;
	settledState: SettledTerminalState;
	terminalEventId?: string;
	reportPath?: string;
	protocolViolationReason?: string;
}

export interface TerminalNotificationState {
	deliveredEventIds?: string[];
	terminalNotificationDeliveredAt?: string;
	terminalDeliveryKey?: string;
	terminalAgentId?: string;
	terminalReportPath?: string;
	terminalState?: BridgeSettlementState;
	terminalEventId?: string;
	protocolViolationReason?: string;
}

export interface TerminalNotificationIdentity {
	terminalDeliveryKey?: string;
	terminalAgentId?: string;
	terminalReportPath?: string;
	terminalState: SettledTerminalState;
	terminalEventId?: string;
	protocolViolationReason?: string;
}

export interface InactivityWatchdogDecisionInput {
	activity: Pick<AgentActivitySnapshot, "activityState" | "quietForMs">;
	lastActivity: string;
	lastNotifiedAt?: string;
	nowMs: number;
	thresholdMs: number;
}

export interface ParentDeliveryFlushOptions<TDelivery extends QueuedParentDelivery> {
	queue: Map<string, TDelivery>;
	makeBatchId: () => string;
	updateTerminalNotificationState: (deliveries: TDelivery[], batchId: string, phase: "queued" | "delivered") => Promise<void>;
	sendParentMessage: (batchId: string, deliveries: TDelivery[]) => void;
	markTerminalDeliveriesSent?: (deliveries: TDelivery[]) => void;
	markParentDeliveriesDelivered: (deliveries: TDelivery[]) => Promise<void>;
	scheduleRetry: () => void;
}

export interface ParentDeliveryFlushResult<TDelivery extends QueuedParentDelivery> {
	batchId?: string;
	deliveries: TDelivery[];
	sent: boolean;
}

export function shouldSendStatusRequestProbe(
	activity: Pick<AgentActivitySnapshot, "bridgeSettlementState" | "activityState">,
): boolean {
	return activity.bridgeSettlementState === "running"
		&& activity.activityState !== "terminated"
		&& activity.activityState !== "missing_session";
}

function keyPart(value: string | undefined): string {
	return encodeURIComponent(value?.trim() || "unknown");
}

export function buildTerminalDeliveryKey(identity: TerminalDeliveryIdentityInput): string {
	if (identity.terminalEventId?.trim()) {
		return [
			"terminal",
			identity.agentId?.trim() ? `agent=${keyPart(identity.agentId)}` : `bridge=${keyPart(identity.bridgeDir)}`,
			`state=${keyPart(identity.settledState)}`,
			`event=${keyPart(identity.terminalEventId)}`,
		].join(":");
	}
	return [
		"terminal",
		`bridge=${keyPart(identity.bridgeDir)}`,
		`agent=${keyPart(identity.agentId)}`,
		`state=${keyPart(identity.settledState)}`,
		`reason=${keyPart(identity.protocolViolationReason)}`,
		`report=${keyPart(identity.reportPath)}`,
	].join(":");
}

export function hasDeliveredTerminalNotification(
	parentState: TerminalNotificationState,
	identity: TerminalNotificationIdentity,
): boolean {
	const hasDeliveredMarker = Boolean(parentState.terminalNotificationDeliveredAt)
		|| Boolean(identity.terminalEventId && parentState.deliveredEventIds?.includes(identity.terminalEventId));
	if (!hasDeliveredMarker) return false;
	if (identity.terminalDeliveryKey && parentState.terminalDeliveryKey) {
		return parentState.terminalDeliveryKey === identity.terminalDeliveryKey;
	}
	return parentState.terminalState === identity.terminalState
		&& parentState.terminalEventId === identity.terminalEventId
		&& parentState.protocolViolationReason === identity.protocolViolationReason;
}

export function shouldNotifyInactivityWatchdog(input: InactivityWatchdogDecisionInput): boolean {
	if (input.activity.activityState !== "running_quiet" || input.activity.quietForMs === undefined) return false;
	if (!input.lastNotifiedAt) return true;
	const lastNotifiedMs = Date.parse(input.lastNotifiedAt);
	if (!Number.isFinite(lastNotifiedMs)) return true;
	return !(input.lastNotifiedAt >= input.lastActivity && input.nowMs - lastNotifiedMs < input.thresholdMs);
}

export async function flushQueuedParentDeliveries<TDelivery extends QueuedParentDelivery>(
	options: ParentDeliveryFlushOptions<TDelivery>,
): Promise<ParentDeliveryFlushResult<TDelivery>> {
	if (options.queue.size === 0) return { deliveries: [], sent: false };
	const deliveries = [...options.queue.values()].sort((left, right) => left.createdAt.localeCompare(right.createdAt) || left.key.localeCompare(right.key));
	const batchId = options.makeBatchId();
	options.queue.clear();
	let sendCompleted = false;
	try {
		await options.updateTerminalNotificationState(deliveries, batchId, "queued");
		options.sendParentMessage(batchId, deliveries);
		sendCompleted = true;
		options.markTerminalDeliveriesSent?.(deliveries);
		await options.markParentDeliveriesDelivered(deliveries);
		await options.updateTerminalNotificationState(deliveries, batchId, "delivered");
		return { batchId, deliveries, sent: true };
	} catch (error) {
		const retryableDeliveries = sendCompleted ? deliveries.filter((delivery) => !delivery.terminalDeliveryKey) : deliveries;
		for (const delivery of retryableDeliveries) options.queue.set(delivery.key, delivery);
		if (retryableDeliveries.length > 0) options.scheduleRetry();
		throw error;
	}
}

