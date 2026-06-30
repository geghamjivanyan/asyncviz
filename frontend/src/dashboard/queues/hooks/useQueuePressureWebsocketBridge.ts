/**
 * Websocket subscription factory for queue-metrics aggregate events.
 *
 * Queue-metrics events ride on ``runtime_event`` envelopes whose
 * payload is a serialized Pydantic ``RuntimeEvent`` subclass — the
 * actual wire payload is the envelope's ``payload`` itself, *not* a
 * nested ``payload.payload`` (the queue-metrics events publish the
 * full payload flat, not as ``GenericEvent``).
 *
 * Factory-style construction mirrors
 * :func:`useBlockingWarningWebsocketBridge`: tests inject a stub
 * source, production wires the real :func:`useWebSocketClient`.
 */

import { useEffect, useMemo } from "react";
import { useWebSocketClient } from "@/app/providers/RuntimeProvider";
import type { RuntimeEnvelope } from "@/types/runtime";
import type {
  QueueMetricsEventPayload,
  QueueMetricsEventType,
} from "@/dashboard/queues/models/QueuePressureModels";
import { QUEUE_METRICS_EVENT_TYPES } from "@/dashboard/queues/models/QueuePressureModels";
import { useQueuePressureStore } from "@/dashboard/queues/QueuePressureStore";
import { getQueuePressurePanelMetrics } from "@/dashboard/queues/diagnostics/QueuePressureMetricsCollector";
import { recordQueuePressureTrace } from "@/dashboard/queues/diagnostics/QueuePressureTracing";

export interface QueuePressureEnvelopeSource {
  subscribe(
    filter: "runtime_event",
    listener: (envelope: RuntimeEnvelope) => void,
  ): { unsubscribe: () => void };
}

const QUEUE_METRICS_TYPE_SET: ReadonlySet<string> = new Set(QUEUE_METRICS_EVENT_TYPES);

/**
 * Coerce a ``runtime_event`` envelope into a queue-metrics payload.
 *
 * The envelope.payload IS the wire payload (Pydantic serializes the
 * RuntimeEvent subclass directly, with ``event_type`` as a discriminator
 * field). Returns ``null`` for envelopes that aren't queue-metrics
 * events so the hot path stays branch-free.
 */
export function queueMetricsPayloadFromEnvelope(
  envelope: RuntimeEnvelope,
): QueueMetricsEventPayload | null {
  const payload = envelope.payload as { event_type?: string } | undefined;
  if (payload === undefined) return null;
  const eventType = payload.event_type;
  if (typeof eventType !== "string") return null;
  if (!QUEUE_METRICS_TYPE_SET.has(eventType)) return null;
  return payload as unknown as QueueMetricsEventPayload;
}

export type QueuePressureSubscribeFactory = (
  apply: (payload: QueueMetricsEventPayload) => void,
) => () => void;

export function makeQueuePressureSubscribeFactory(
  source: QueuePressureEnvelopeSource,
): QueuePressureSubscribeFactory {
  return (apply) => {
    const sub = source.subscribe("runtime_event", (envelope) => {
      const payload = queueMetricsPayloadFromEnvelope(envelope);
      if (payload !== null) apply(payload);
    });
    return () => sub.unsubscribe();
  };
}

export interface UseQueuePressureWebsocketBridgeOptions {
  enabled?: boolean;
  /** Test-only override — defaults to the real client from the provider. */
  subscribe?: QueuePressureSubscribeFactory;
}

/**
 * Subscribe to queue-metrics events on the runtime websocket + fold
 * each payload into the store. Idempotent: re-runs unsubscribe + re-
 * subscribes when ``subscribe`` factory identity changes.
 */
export function useQueuePressureWebsocketBridge(
  options: UseQueuePressureWebsocketBridgeOptions = {},
): void {
  const { enabled = true, subscribe: subscribeOverride } = options;
  const client = useWebSocketClient();
  const applyEventPayload = useQueuePressureStore((s) => s.applyEventPayload);
  const factory = useMemo<QueuePressureSubscribeFactory | undefined>(
    () => (enabled ? (subscribeOverride ?? makeQueuePressureSubscribeFactory(client)) : undefined),
    [enabled, subscribeOverride, client],
  );

  useEffect(() => {
    if (factory === undefined) return undefined;
    const panelMetrics = getQueuePressurePanelMetrics();
    const unsubscribe = factory((payload) => {
      panelMetrics.recordWebsocketEvent();
      recordQueuePressureTrace({
        kind: "ws-payload-applied",
        detail: `${payload.event_type as QueueMetricsEventType}:${payload.queue_id}`,
      });
      applyEventPayload(payload);
    });
    return unsubscribe;
  }, [factory, applyEventPayload]);
}
