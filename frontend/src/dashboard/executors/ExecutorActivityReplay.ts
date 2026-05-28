/**
 * Replay-mode reconciliation helpers for the executor activity store.
 */

import type { ExecutorActivityEventPayload } from "@/dashboard/executors/models/ExecutorActivityModels";
import { useExecutorActivityStore } from "@/dashboard/executors/ExecutorActivityStore";

export function resetForReplay(): void {
  useExecutorActivityStore.getState().reset();
}

export function replayEventPayload(payload: ExecutorActivityEventPayload): void {
  useExecutorActivityStore.getState().applyEventPayload(payload);
}

export function replayEventStream(
  payloads: Iterable<ExecutorActivityEventPayload>,
): void {
  const apply = useExecutorActivityStore.getState().applyEventPayload;
  for (const payload of payloads) apply(payload);
}
