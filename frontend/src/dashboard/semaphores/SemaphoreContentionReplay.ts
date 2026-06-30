/**
 * Replay-mode reconciliation helpers for the semaphore contention store.
 *
 * Same shape as the queue layer — the live ``applyEventPayload`` path
 * is already replay-safe (idempotent by ``semaphore_id`` + sequence),
 * so replay just needs a one-shot reset before the playback head
 * jumps backward.
 */

import type { SemaphoreEventPayload } from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import { useSemaphoreContentionStore } from "@/dashboard/semaphores/SemaphoreContentionStore";

export function resetForReplay(): void {
  useSemaphoreContentionStore.getState().reset();
}

export function replayEventPayload(payload: SemaphoreEventPayload): void {
  useSemaphoreContentionStore.getState().applyEventPayload(payload);
}

export function replayEventStream(payloads: Iterable<SemaphoreEventPayload>): void {
  const apply = useSemaphoreContentionStore.getState().applyEventPayload;
  for (const payload of payloads) apply(payload);
}
