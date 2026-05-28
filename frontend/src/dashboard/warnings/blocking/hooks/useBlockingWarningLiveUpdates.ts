/**
 * Live-update hook.
 *
 * Subscribes to the runtime store's task-event ring + the existing
 * warning-delta stream is not enough for the emitter's lifecycle
 * events because they ride on ``runtime_event`` envelopes (not on
 * ``warning_delta``). So we read directly from the store's event ring
 * — which today carries only task events — and additionally allow
 * tests to feed payloads via :func:`injectBlockingWarningEvent`.
 *
 * Future task 6.6 will plumb the dedicated ``blocking_warning_delta``
 * envelope through :class:`RuntimeStreamingEngine` and consumers will
 * subscribe to that instead. For now, the hook is wired to be ready
 * for both paths: it accepts an optional ``subscribe`` factory that
 * the websocket binding can swap in.
 */

import { useEffect, useRef } from "react";
import type { BlockingWarningEventPayload } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import { recordBlockingWarningTrace } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";
import { getBlockingWarningPanelMetrics } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";

/** Pluggable subscription factory; returns an unsubscribe callback. */
export type BlockingWarningSubscribeFactory = (
  apply: (payload: BlockingWarningEventPayload) => void,
) => () => void;

/**
 * Module-scoped fan-out so tests + future websocket plumbing can call
 * :func:`injectBlockingWarningEvent` from anywhere. The hook
 * registers a handler on mount; the handler forwards into the store
 * via the store's action.
 */
const _liveSubscribers = new Set<(payload: BlockingWarningEventPayload) => void>();

/** Dispatch a payload to every live subscriber. */
export function injectBlockingWarningEvent(payload: BlockingWarningEventPayload): void {
  for (const subscriber of _liveSubscribers) {
    subscriber(payload);
  }
}

export function useBlockingWarningLiveUpdates(
  options: { subscribe?: BlockingWarningSubscribeFactory } = {},
): void {
  const { subscribe } = options;
  const applyEventPayload = useBlockingWarningStore((s) => s.applyEventPayload);
  const lastSeqRef = useRef(0);

  useEffect(() => {
    const handler = (payload: BlockingWarningEventPayload) => {
      const metrics = getBlockingWarningPanelMetrics();
      const previous = lastSeqRef.current;
      applyEventPayload(payload);
      // Read the post-update sequence so we can decide whether the
      // event was actually applied or rejected by the store's gate.
      const next = useBlockingWarningStore.getState().lastSequence;
      if (next > previous) {
        lastSeqRef.current = next;
        metrics.recordLiveEvent();
        recordBlockingWarningTrace({
          kind: "event-applied",
          detail: `${payload.transition}:${payload.group_id}:${payload.sequence}`,
        });
      } else {
        metrics.recordLiveEventDropped();
        recordBlockingWarningTrace({
          kind: "event-dropped",
          detail: `${payload.transition}:${payload.group_id}:${payload.sequence}`,
        });
      }
    };
    _liveSubscribers.add(handler);
    const unsubExternal = subscribe ? subscribe(handler) : undefined;
    return () => {
      _liveSubscribers.delete(handler);
      if (unsubExternal) unsubExternal();
    };
  }, [applyEventPayload, subscribe]);
}
