/**
 * Types for the live timeline update engine.
 *
 * The shapes here are the *contract surface* between the realtime
 * pieces (delta processor, replay coordinator, invalidation tracker,
 * animation clock) and the canvas renderer. Keeping them in one
 * file means new realtime callers can find the surface in one place.
 */

/** What kind of change triggered an invalidation. Mirrors but extends
 *  the renderer's :type:`DirtyReason`. */
export type InvalidationReason =
  | "row"
  | "segment"
  | "viewport"
  | "selection"
  | "warning"
  | "replay"
  | "active-tick"
  | "manual"
  | "delta-batch"
  | "hydration";

/** A dirty region marked by the engine. */
export interface DirtyRegion {
  reason: InvalidationReason;
  /** Optional task id(s) the change touched. */
  taskIds?: readonly string[];
  /** Optional segment id(s) the change touched. */
  segmentIds?: readonly string[];
  /** When the change happened (monotonic ms). */
  atMs: number;
  /** Sequence cursor the change references, when applicable. */
  sequence?: number | null;
}

/** Snapshot of the engine's mode. */
export type TimelineLiveMode = "idle" | "live" | "replay" | "paused";

/** Replay transition state. */
export type TimelineReplayPhase = "idle" | "buffering" | "applying" | "transitioning" | "done";

/** Coalesced batch the engine flushes to the renderer. */
export interface InvalidationBatch {
  /** Distinct reasons present in the batch. */
  reasons: readonly InvalidationReason[];
  /** Unique task ids touched. */
  taskIds: readonly string[];
  /** Unique segment ids touched. */
  segmentIds: readonly string[];
  /** Highest sequence cursor referenced. */
  highestSequence: number;
  /** Total dirty regions absorbed into the batch. */
  regionCount: number;
  /** Whether the batch includes a viewport-scope invalidation. */
  includesViewport: boolean;
  /** Whether the batch includes an active-tick invalidation. */
  includesActiveTick: boolean;
}

/** Stable empty batch sentinel — safe to return when nothing is dirty. */
export const EMPTY_INVALIDATION_BATCH: InvalidationBatch = Object.freeze({
  reasons: Object.freeze([]) as readonly InvalidationReason[],
  taskIds: Object.freeze([]) as readonly string[],
  segmentIds: Object.freeze([]) as readonly string[],
  highestSequence: 0,
  regionCount: 0,
  includesViewport: false,
  includesActiveTick: false,
});
