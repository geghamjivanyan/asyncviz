/**
 * Websocket subscription factory for gather events.
 *
 * Gather events ride on ``runtime_event`` envelopes whose payload IS
 * the wire payload (Pydantic ``RuntimeEvent`` subclass serialized with
 * ``event_type`` as the discriminator).
 */

import { useEffect, useMemo } from "react";
import { useWebSocketClient } from "@/app/providers/RuntimeProvider";
import type { RuntimeEnvelope } from "@/types/runtime";
import {
  GATHER_EVENT_TYPES,
  type AwaitGatherEventPayload,
  type GatherEventType,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";
import { useAwaitDependencyStore } from "@/dashboard/dependencies/AwaitDependencyStore";
import { getAwaitDependencyPanelMetrics } from "@/dashboard/dependencies/diagnostics/AwaitDependencyMetricsCollector";
import { recordAwaitDependencyTrace } from "@/dashboard/dependencies/diagnostics/AwaitDependencyTracing";

export interface AwaitDependencyEnvelopeSource {
  subscribe(
    filter: "runtime_event",
    listener: (envelope: RuntimeEnvelope) => void,
  ): { unsubscribe: () => void };
}

const GATHER_TYPE_SET: ReadonlySet<string> = new Set(GATHER_EVENT_TYPES);

export function gatherPayloadFromEnvelope(
  envelope: RuntimeEnvelope,
): AwaitGatherEventPayload | null {
  const payload = envelope.payload as { event_type?: string } | undefined;
  if (payload === undefined) return null;
  const eventType = payload.event_type;
  if (typeof eventType !== "string") return null;
  if (!GATHER_TYPE_SET.has(eventType)) return null;
  return payload as unknown as AwaitGatherEventPayload;
}

export type AwaitDependencySubscribeFactory = (
  apply: (payload: AwaitGatherEventPayload) => void,
) => () => void;

export function makeAwaitDependencySubscribeFactory(
  source: AwaitDependencyEnvelopeSource,
): AwaitDependencySubscribeFactory {
  return (apply) => {
    const sub = source.subscribe("runtime_event", (envelope) => {
      const payload = gatherPayloadFromEnvelope(envelope);
      if (payload !== null) apply(payload);
    });
    return () => sub.unsubscribe();
  };
}

export interface UseAwaitDependencyWebsocketBridgeOptions {
  enabled?: boolean;
  subscribe?: AwaitDependencySubscribeFactory;
}

export function useAwaitDependencyWebsocketBridge(
  options: UseAwaitDependencyWebsocketBridgeOptions = {},
): void {
  const { enabled = true, subscribe: subscribeOverride } = options;
  const client = useWebSocketClient();
  const applyEventPayload = useAwaitDependencyStore((s) => s.applyEventPayload);
  const factory = useMemo<AwaitDependencySubscribeFactory | undefined>(
    () =>
      enabled ? (subscribeOverride ?? makeAwaitDependencySubscribeFactory(client)) : undefined,
    [enabled, subscribeOverride, client],
  );

  useEffect(() => {
    if (factory === undefined) return undefined;
    const metrics = getAwaitDependencyPanelMetrics();
    const unsubscribe = factory((payload) => {
      metrics.recordWebsocketEvent();
      recordAwaitDependencyTrace({
        kind: "ws-payload-applied",
        detail: `${payload.event_type as GatherEventType}:${payload.gather_id}`,
      });
      applyEventPayload(payload);
    });
    return unsubscribe;
  }, [factory, applyEventPayload]);
}
