/**
 * Filtering, search, sorting and grouping state for the event feed.
 *
 * Everything here is value-only — reducers consume the state, never
 * mutate it. Defaults are explicit so replays produce the same UI
 * every time.
 */

import type { EventCategory, EventRowIntent } from "@/dashboard/events/models/eventRow";

export type EventSortDirection = "newest" | "oldest";

export interface EventFilterState {
  /** When non-null, restrict to these categories. */
  categories: readonly EventCategory[] | null;
  /** Free-form text search across the row's label / task id / event id. */
  search: string;
  /** Keep only rows that link to at least one warning. */
  warningsOnly: boolean;
  /** Keep only rows produced from a replay batch. */
  replayOnly: boolean;
  /** Keep only terminal task events (completed/cancelled/failed). */
  terminalOnly: boolean;
  /** Keep only rows whose linked task is currently active in the timeline. */
  activeTimelineOnly: boolean;
  /** Restrict to a specific task id. ``null`` means no restriction. */
  taskId: string | null;
  /** Intent restriction — used by the severity badges in the toolbar. */
  intents: readonly EventRowIntent[] | null;
}

export const DEFAULT_EVENT_FILTERS: EventFilterState = {
  categories: null,
  search: "",
  warningsOnly: false,
  replayOnly: false,
  terminalOnly: false,
  activeTimelineOnly: false,
  taskId: null,
  intents: null,
};

export interface EventSortState {
  direction: EventSortDirection;
}

export const DEFAULT_EVENT_SORT: EventSortState = { direction: "newest" };

export type EventGroupingMode = "none" | "task" | "category" | "replay-batch";

export interface EventGroupingState {
  mode: EventGroupingMode;
}

export const DEFAULT_EVENT_GROUPING: EventGroupingState = { mode: "none" };

/** Pure: ``true`` when no filter is set — fast-path the pipeline. */
export function isDefaultEventFilterState(filters: EventFilterState): boolean {
  return (
    filters.categories === null &&
    filters.search === "" &&
    !filters.warningsOnly &&
    !filters.replayOnly &&
    !filters.terminalOnly &&
    !filters.activeTimelineOnly &&
    filters.taskId === null &&
    filters.intents === null
  );
}
