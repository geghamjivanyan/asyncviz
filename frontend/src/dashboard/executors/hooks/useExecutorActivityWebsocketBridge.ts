/**
 * Websocket subscription factory for executor-metrics aggregate events.
 *
 * Same envelope shape as queue + semaphore: ``runtime_event`` envelope
 * with the wire payload at ``envelope.payload`` and a discriminator
 * ``event_type`` field.
 */

import { useEffect, useMemo } from "react";
import { useWebSocketClient } from "@/app/providers/RuntimeProvider";
import type { RuntimeEnvelope } from "@/types/runtime";
import {
  EXECUTOR_METRICS_EVENT_TYPES,
  type ExecutorActivityEventPayload,
  type ExecutorActivityEventType,
} from "@/dashboard/executors/models/ExecutorActivityModels";
import { useExecutorActivityStore } from "@/dashboard/executors/ExecutorActivityStore";
import { getExecutorActivityPanelMetrics } from "@/dashboard/executors/diagnostics/ExecutorActivityMetricsCollector";
import { recordExecutorActivityTrace } from "@/dashboard/executors/diagnostics/ExecutorActivityTracing";

export interface ExecutorActivityEnvelopeSource {
  subscribe(
    filter: "runtime_event",
    listener: (envelope: RuntimeEnvelope) => void,
  ): { unsubscribe: () => void };
}

const EXECUTOR_TYPE_SET: ReadonlySet<string> = new Set(EXECUTOR_METRICS_EVENT_TYPES);

export function executorActivityPayloadFromEnvelope(
  envelope: RuntimeEnvelope,
): ExecutorActivityEventPayload | null {
  const payload = envelope.payload as { event_type?: string } | undefined;
  if (payload === undefined) return null;
  const eventType = payload.event_type;
  if (typeof eventType !== "string") return null;
  if (!EXECUTOR_TYPE_SET.has(eventType)) return null;
  return payload as unknown as ExecutorActivityEventPayload;
}

export type ExecutorActivitySubscribeFactory = (
  apply: (payload: ExecutorActivityEventPayload) => void,
) => () => void;

export function makeExecutorActivitySubscribeFactory(
  source: ExecutorActivityEnvelopeSource,
): ExecutorActivitySubscribeFactory {
  return (apply) => {
    const sub = source.subscribe("runtime_event", (envelope) => {
      const payload = executorActivityPayloadFromEnvelope(envelope);
      if (payload !== null) apply(payload);
    });
    return () => sub.unsubscribe();
  };
}

export interface UseExecutorActivityWebsocketBridgeOptions {
  enabled?: boolean;
  subscribe?: ExecutorActivitySubscribeFactory;
}

export function useExecutorActivityWebsocketBridge(
  options: UseExecutorActivityWebsocketBridgeOptions = {},
): void {
  const { enabled = true, subscribe: subscribeOverride } = options;
  const client = useWebSocketClient();
  const applyEventPayload = useExecutorActivityStore((s) => s.applyEventPayload);
  const factory = useMemo<ExecutorActivitySubscribeFactory | undefined>(
    () =>
      enabled ? (subscribeOverride ?? makeExecutorActivitySubscribeFactory(client)) : undefined,
    [enabled, subscribeOverride, client],
  );

  useEffect(() => {
    if (factory === undefined) return undefined;
    const metrics = getExecutorActivityPanelMetrics();
    const unsubscribe = factory((payload) => {
      metrics.recordWebsocketEvent();
      recordExecutorActivityTrace({
        kind: "ws-payload-applied",
        detail: `${payload.event_type as ExecutorActivityEventType}:${payload.executor_id}`,
      });
      applyEventPayload(payload);
    });
    return unsubscribe;
  }, [factory, applyEventPayload]);
}
