/**
 * Replay-mode reconciliation helpers for the dependency-graph store.
 *
 * The live ``applyEventPayload`` path is already replay-safe; replay
 * just needs a one-shot reset before the playback head jumps backward.
 */

import type { AwaitGatherEventPayload } from "@/dashboard/dependencies/models/AwaitDependencyModels";
import { useAwaitDependencyStore } from "@/dashboard/dependencies/AwaitDependencyStore";

export function resetForReplay(): void {
  useAwaitDependencyStore.getState().reset();
}

export function replayEventPayload(payload: AwaitGatherEventPayload): void {
  useAwaitDependencyStore.getState().applyEventPayload(payload);
}

export function replayEventStream(
  payloads: Iterable<AwaitGatherEventPayload>,
): void {
  const apply = useAwaitDependencyStore.getState().applyEventPayload;
  for (const payload of payloads) apply(payload);
}
