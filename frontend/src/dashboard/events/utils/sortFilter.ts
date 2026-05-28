/**
 * Sort + filter pipeline for the event feed.
 *
 * All functions are pure and operate on :type:`EventRow[]` arrays.
 * Sorting is stable; the pipeline is filter → sort so the (possibly
 * O(n log n)) sort runs on the smaller candidate set.
 */

import {
  compareEventRowsNewestFirst,
  compareEventRowsOldestFirst,
  type EventRow,
} from "@/dashboard/events/models/eventRow";
import {
  isDefaultEventFilterState,
  type EventFilterState,
  type EventSortState,
} from "@/dashboard/events/models/filters";

export function filterEventRows(rows: readonly EventRow[], filters: EventFilterState): EventRow[] {
  if (isDefaultEventFilterState(filters)) {
    return rows.slice();
  }
  const needle = filters.search.trim().toLowerCase();
  const categorySet = filters.categories === null ? null : new Set(filters.categories);
  const intentSet = filters.intents === null ? null : new Set(filters.intents);
  const out: EventRow[] = [];
  for (const row of rows) {
    if (categorySet !== null && !categorySet.has(row.category)) continue;
    if (intentSet !== null && !intentSet.has(row.intent)) continue;
    if (filters.warningsOnly && row.warnings.count === 0) continue;
    if (filters.replayOnly && row.source !== "replay") continue;
    if (filters.terminalOnly && !row.isTerminal) continue;
    if (filters.activeTimelineOnly && !row.timeline.hasActiveSegment) continue;
    if (filters.taskId !== null && row.taskId !== filters.taskId) continue;
    if (needle !== "") {
      const hay =
        `${row.label} ${row.eventType} ${row.taskId} ${row.eventId} ${row.coroutineName ?? ""}`.toLowerCase();
      if (!hay.includes(needle)) continue;
    }
    out.push(row);
  }
  return out;
}

export function sortEventRows(rows: readonly EventRow[], sort: EventSortState): EventRow[] {
  const out = rows.slice();
  out.sort(sort.direction === "newest" ? compareEventRowsNewestFirst : compareEventRowsOldestFirst);
  return out;
}

export function applyEventFilterAndSort(
  rows: readonly EventRow[],
  filters: EventFilterState,
  sort: EventSortState,
): EventRow[] {
  return sortEventRows(filterEventRows(rows, filters), sort);
}
