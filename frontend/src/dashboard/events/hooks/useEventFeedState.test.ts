import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useEventFeedState } from "@/dashboard/events/hooks/useEventFeedState";
import {
  DEFAULT_EVENT_FILTERS,
  DEFAULT_EVENT_GROUPING,
  DEFAULT_EVENT_SORT,
} from "@/dashboard/events/models/filters";

describe("useEventFeedState", () => {
  it("starts at the defaults", () => {
    const { result } = renderHook(() => useEventFeedState());
    expect(result.current.filters).toEqual(DEFAULT_EVENT_FILTERS);
    expect(result.current.sort).toEqual(DEFAULT_EVENT_SORT);
    expect(result.current.grouping).toEqual(DEFAULT_EVENT_GROUPING);
  });

  it("setFilters merges", () => {
    const { result } = renderHook(() => useEventFeedState());
    act(() => result.current.setFilters({ warningsOnly: true }));
    expect(result.current.filters.warningsOnly).toBe(true);
    act(() => result.current.setFilters({ search: "x" }));
    expect(result.current.filters.warningsOnly).toBe(true);
    expect(result.current.filters.search).toBe("x");
  });

  it("toggleSort flips the direction", () => {
    const { result } = renderHook(() => useEventFeedState());
    expect(result.current.sort.direction).toBe("newest");
    act(() => result.current.toggleSort());
    expect(result.current.sort.direction).toBe("oldest");
  });

  it("setGrouping updates the mode", () => {
    const { result } = renderHook(() => useEventFeedState());
    act(() => result.current.setGrouping({ mode: "task" }));
    expect(result.current.grouping.mode).toBe("task");
  });

  it("resetFilters returns to defaults", () => {
    const { result } = renderHook(() => useEventFeedState());
    act(() => result.current.setFilters({ warningsOnly: true, search: "x" }));
    act(() => result.current.resetFilters());
    expect(result.current.filters).toEqual(DEFAULT_EVENT_FILTERS);
  });
});
