/**
 * Sequence-aware envelope filter for the store.
 *
 * Wraps the websocket client's :class:`SequenceTracker` with the
 * minimum additional state the store needs: the store records its own
 * ``lastSequence`` cursor so it can render "what sequence is the
 * dashboard at" without coupling to the websocket client instance.
 *
 * The websocket client already drops duplicates and stale frames
 * before fanning out. This module exists as the *store-side* safety
 * net for two cases:
 *
 *   1. Envelopes injected by tests / replay tools that bypass the
 *      websocket client entirely.
 *   2. Replay-batch reconciliation where the store receives a list of
 *      already-ordered frames + must filter against its current
 *      cursor without re-running them through the websocket client.
 */

import type { RuntimeEnvelope } from "@/types/runtime";

export type StoreSequenceDecision = "accept" | "duplicate" | "stale" | "out-of-order";

export function decideStoreSequence(
  envelope: RuntimeEnvelope,
  lastSequence: number,
): StoreSequenceDecision {
  const seq = envelope.sequence;
  if (seq === null || seq === undefined) return "accept";
  if (seq > lastSequence + 1) return "out-of-order";
  if (seq === lastSequence + 1) return "accept";
  if (seq === lastSequence) return "duplicate";
  return "stale";
}

/** Take a maximum, treating ``null`` / ``undefined`` as 0. */
export function maxSequence(a: number, b: number | null | undefined): number {
  if (b === null || b === undefined) return a;
  return b > a ? b : a;
}
