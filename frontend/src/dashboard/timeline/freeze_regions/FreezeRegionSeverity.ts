/**
 * Severity / lifecycle helpers for freeze regions.
 *
 * The mapping from emitter severity → render intent mirrors the
 * blocking-warning panel (so the canvas overlay and the panel card
 * agree visually). Lifecycle handling collapses
 * opened/escalating/active → ``"active"`` and recovered/expired →
 * ``"recovered"`` since the renderer treats them uniformly.
 */

import type {
  BlockingGroupSeverity,
  BlockingGroupState,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import type {
  FreezeRegionIntent,
  FreezeRegionLifecycle,
} from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

const TERMINAL: ReadonlySet<BlockingGroupState> = new Set(["recovered", "expired"]);

const SEVERITY_RANK: Record<BlockingGroupSeverity, number> = {
  NONE: 0,
  WARNING: 1,
  CRITICAL: 2,
  FREEZE: 3,
};

/** True when ``state`` is a terminal (closed) lifecycle state. */
export function isTerminalState(state: BlockingGroupState): boolean {
  return TERMINAL.has(state);
}

/** Map a lifecycle state to the renderer's active/recovered bucket. */
export function lifecycleForState(state: BlockingGroupState): FreezeRegionLifecycle {
  return TERMINAL.has(state) ? "recovered" : "active";
}

/**
 * Map severity + state to a freeze-region intent.
 *
 * Terminal states fold to ``"resolved"`` regardless of peak severity —
 * the operator doesn't need to act on them, so they dim uniformly.
 */
export function intentForFreeze(
  severity: BlockingGroupSeverity,
  state: BlockingGroupState,
): FreezeRegionIntent {
  if (TERMINAL.has(state)) return "resolved";
  if (severity === "FREEZE") return "freeze";
  if (severity === "CRITICAL") return "critical";
  // Anything weaker than warning is filtered out before projection;
  // the renderer normalizes to warning so styling stays in the table.
  return "warning";
}

/**
 * Sort order: active before recovered; within bucket, higher severity
 * first; ties broken by earlier ``firstSeenNs``. Pure function — used
 * by the renderer to draw recovered regions *first* so active overlays
 * render on top.
 */
export interface CompareKey {
  lifecycle: FreezeRegionLifecycle;
  severity: BlockingGroupSeverity;
  firstSeenNs: number;
}

export function compareFreezeKeys(a: CompareKey, b: CompareKey): number {
  if (a.lifecycle !== b.lifecycle) {
    return a.lifecycle === "active" ? -1 : 1;
  }
  const sevDelta = SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity];
  if (sevDelta !== 0) return sevDelta;
  return a.firstSeenNs - b.firstSeenNs;
}
