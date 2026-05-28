/**
 * Websocket subscription factory for semaphore wire events.
 *
 * Semaphore events ride on ``runtime_event`` envelopes whose payload
 * IS the wire payload (the Pydantic ``RuntimeEvent`` subclass is
 * serialized directly, with ``event_type`` as the discriminator).
 */

import { useEffect, useMemo } from "react";
import { useWebSocketClient } from "@/app/providers/RuntimeProvider";
import type { RuntimeEnvelope } from "@/types/runtime";
import {
  SEMAPHORE_EVENT_TYPES,
  type SemaphoreEventPayload,
  type SemaphoreEventType,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import { useSemaphoreContentionStore } from "@/dashboard/semaphores/SemaphoreContentionStore";
import { getSemaphoreContentionPanelMetrics } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionMetricsCollector";
import { recordSemaphoreContentionTrace } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionTracing";

export interface SemaphoreContentionEnvelopeSource {
  subscribe(
    filter: "runtime_event",
    listener: (envelope: RuntimeEnvelope) => void,
  ): { unsubscribe: () => void };
}

const SEMAPHORE_TYPE_SET: ReadonlySet<string> = new Set(SEMAPHORE_EVENT_TYPES);

export function semaphorePayloadFromEnvelope(
  envelope: RuntimeEnvelope,
): SemaphoreEventPayload | null {
  const payload = envelope.payload as { event_type?: string } | undefined;
  if (payload === undefined) return null;
  const eventType = payload.event_type;
  if (typeof eventType !== "string") return null;
  if (!SEMAPHORE_TYPE_SET.has(eventType)) return null;
  return payload as unknown as SemaphoreEventPayload;
}

export type SemaphoreContentionSubscribeFactory = (
  apply: (payload: SemaphoreEventPayload) => void,
) => () => void;

export function makeSemaphoreContentionSubscribeFactory(
  source: SemaphoreContentionEnvelopeSource,
): SemaphoreContentionSubscribeFactory {
  return (apply) => {
    const sub = source.subscribe("runtime_event", (envelope) => {
      const payload = semaphorePayloadFromEnvelope(envelope);
      if (payload !== null) apply(payload);
    });
    return () => sub.unsubscribe();
  };
}

export interface UseSemaphoreContentionWebsocketBridgeOptions {
  enabled?: boolean;
  subscribe?: SemaphoreContentionSubscribeFactory;
}

export function useSemaphoreContentionWebsocketBridge(
  options: UseSemaphoreContentionWebsocketBridgeOptions = {},
): void {
  const { enabled = true, subscribe: subscribeOverride } = options;
  const client = useWebSocketClient();
  const applyEventPayload = useSemaphoreContentionStore((s) => s.applyEventPayload);
  const factory = useMemo<SemaphoreContentionSubscribeFactory | undefined>(
    () =>
      enabled
        ? (subscribeOverride ?? makeSemaphoreContentionSubscribeFactory(client))
        : undefined,
    [enabled, subscribeOverride, client],
  );

  useEffect(() => {
    if (factory === undefined) return undefined;
    const panelMetrics = getSemaphoreContentionPanelMetrics();
    const unsubscribe = factory((payload) => {
      panelMetrics.recordWebsocketEvent();
      recordSemaphoreContentionTrace({
        kind: "ws-payload-applied",
        detail: `${payload.event_type as SemaphoreEventType}:${payload.semaphore_id}`,
      });
      applyEventPayload(payload);
    });
    return unsubscribe;
  }, [factory, applyEventPayload]);
}
