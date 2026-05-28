/**
 * Row interaction semantics.
 *
 * Translates raw pointer hits into the actions the row layer cares
 * about: hover, primary selection, secondary selection (label vs.
 * timeline). The module is the future home for drag selection,
 * grouped-row toggling, and timeline scrubbing — but those land in
 * later tasks; today it's the canonical event resolver.
 */

import type { RowHitTestResult, TimelineRowZone } from "@/dashboard/timeline/rows/TimelineRowHitTesting";

export type RowInteractionKind =
  | "none"
  | "hover-row"
  | "select-row"
  | "select-timeline"
  | "toggle-group";

export interface RowInteractionEvent {
  kind: RowInteractionKind;
  rowId: string | null;
  taskId: string | null;
  zone: TimelineRowZone | null;
  timeSeconds: number | null;
}

const NONE: RowInteractionEvent = {
  kind: "none",
  rowId: null,
  taskId: null,
  zone: null,
  timeSeconds: null,
};

/** Pure: translate a hover hit into an interaction event. */
export function resolveHover(hit: RowHitTestResult): RowInteractionEvent {
  if (hit.row === null) return NONE;
  return {
    kind: "hover-row",
    rowId: hit.row.rowId,
    taskId: hit.row.taskId,
    zone: hit.zone,
    timeSeconds: hit.timeSeconds,
  };
}

/** Pure: translate a primary click into a selection event. */
export function resolvePrimaryClick(hit: RowHitTestResult): RowInteractionEvent {
  if (hit.row === null) return NONE;
  if (hit.zone === "timeline") {
    return {
      kind: "select-timeline",
      rowId: hit.row.rowId,
      taskId: hit.row.taskId,
      zone: hit.zone,
      timeSeconds: hit.timeSeconds,
    };
  }
  return {
    kind: "select-row",
    rowId: hit.row.rowId,
    taskId: hit.row.taskId,
    zone: hit.zone,
    timeSeconds: null,
  };
}
