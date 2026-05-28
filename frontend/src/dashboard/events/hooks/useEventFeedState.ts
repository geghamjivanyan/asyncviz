/**
 * Local sort + filter + grouping state for the event feed.
 *
 * Component-local on purpose — UI state, not runtime state.
 */

import { useCallback, useState } from "react";
import {
  DEFAULT_EVENT_FILTERS,
  DEFAULT_EVENT_GROUPING,
  DEFAULT_EVENT_SORT,
  type EventFilterState,
  type EventGroupingState,
  type EventSortState,
} from "@/dashboard/events/models/filters";

export interface EventFeedStateValue {
  filters: EventFilterState;
  sort: EventSortState;
  grouping: EventGroupingState;
  setFilters: (next: Partial<EventFilterState>) => void;
  resetFilters: () => void;
  setSort: (sort: EventSortState) => void;
  toggleSort: () => void;
  setGrouping: (grouping: EventGroupingState) => void;
}

export function useEventFeedState(initial?: {
  filters?: EventFilterState;
  sort?: EventSortState;
  grouping?: EventGroupingState;
}): EventFeedStateValue {
  const [filters, setFiltersState] = useState<EventFilterState>(
    initial?.filters ?? DEFAULT_EVENT_FILTERS,
  );
  const [sort, setSortState] = useState<EventSortState>(initial?.sort ?? DEFAULT_EVENT_SORT);
  const [grouping, setGroupingState] = useState<EventGroupingState>(
    initial?.grouping ?? DEFAULT_EVENT_GROUPING,
  );

  const setFilters = useCallback((next: Partial<EventFilterState>) => {
    setFiltersState((prev) => ({ ...prev, ...next }));
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(DEFAULT_EVENT_FILTERS);
  }, []);

  const setSort = useCallback((next: EventSortState) => {
    setSortState(next);
  }, []);

  const toggleSort = useCallback(() => {
    setSortState((prev) => ({
      direction: prev.direction === "newest" ? "oldest" : "newest",
    }));
  }, []);

  const setGrouping = useCallback((next: EventGroupingState) => {
    setGroupingState(next);
  }, []);

  return {
    filters,
    sort,
    grouping,
    setFilters,
    resetFilters,
    setSort,
    toggleSort,
    setGrouping,
  };
}
