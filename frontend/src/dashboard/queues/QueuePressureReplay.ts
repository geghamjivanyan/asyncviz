/**
 * Replay-mode reconciliation for the queue pressure store.
 *
 * Replay sessions stream the original event timeline back through the
 * runtime websocket; queue metrics events ride along. The store's
 * normal :func:`applyEventPayload` path is already replay-safe —
 * idempotent on a per-(queue_id, sequence) basis — so replay just
 * needs a one-shot reset before the playback head jumps backward.
 *
 * No new wire shapes; this module exists so the playback controller
 * has a typed entry point rather than reaching into the store directly.
 */

import type { QueueMetricsEventPayload } from "@/dashboard/queues/models/QueuePressureModels";
import { useQueuePressureStore } from "@/dashboard/queues/QueuePressureStore";

/** Reset the store. Call before seeking backward in the replay timeline. */
export function resetForReplay(): void {
  useQueuePressureStore.getState().reset();
}

/** Replay one payload. Identical to the live path; kept here for clarity. */
export function replayEventPayload(payload: QueueMetricsEventPayload): void {
  useQueuePressureStore.getState().applyEventPayload(payload);
}

/** Bulk-replay helper — useful for tests + scripted scenarios. */
export function replayEventStream(
  payloads: Iterable<QueueMetricsEventPayload>,
): void {
  const apply = useQueuePressureStore.getState().applyEventPayload;
  for (const payload of payloads) apply(payload);
}
