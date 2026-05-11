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
	terminalEventId?: string;
	settledState?: SettledTerminalState;
	createdAt: string;
}

export interface TerminalNotificationState {
	terminalNotificationDeliveredAt?: string;
	terminalState?: BridgeSettlementState;
	terminalEventId?: string;
	protocolViolationReason?: string;
}

export interface TerminalNotificationIdentity {
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

export function hasDeliveredTerminalNotification(
	parentState: TerminalNotificationState,
	identity: TerminalNotificationIdentity,
): boolean {
	return Boolean(parentState.terminalNotificationDeliveredAt)
		&& parentState.terminalState === identity.terminalState
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
	try {
		await options.updateTerminalNotificationState(deliveries, batchId, "queued");
		options.sendParentMessage(batchId, deliveries);
		await options.markParentDeliveriesDelivered(deliveries);
		await options.updateTerminalNotificationState(deliveries, batchId, "delivered");
		return { batchId, deliveries, sent: true };
	} catch (error) {
		for (const delivery of deliveries) options.queue.set(delivery.key, delivery);
		options.scheduleRetry();
		throw error;
	}
}

