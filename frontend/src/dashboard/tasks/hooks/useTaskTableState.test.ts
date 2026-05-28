import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useTaskTableState } from "@/dashboard/tasks/hooks/useTaskTableState";
import { DEFAULT_FILTERS, DEFAULT_SORT } from "@/dashboard/tasks/models/filters";

describe("useTaskTableState", () => {
  it("starts at the defaults when nothing is passed", () => {
    const { result } = renderHook(() => useTaskTableState());
    expect(result.current.sort).toEqual(DEFAULT_SORT);
    expect(result.current.filters).toEqual(DEFAULT_FILTERS);
  });

  it("toggleSort flips direction when called on the active column", () => {
    const { result } = renderHook(() => useTaskTableState());
    act(() => result.current.toggleSort(result.current.sort.columnId));
    expect(result.current.sort.direction).toBe("asc");
    act(() => result.current.toggleSort(result.current.sort.columnId));
    expect(result.current.sort.direction).toBe("desc");
  });

  it("toggleSort switches to a new column and starts ascending", () => {
    const { result } = renderHook(() => useTaskTableState());
    act(() => result.current.toggleSort("duration"));
    expect(result.current.sort.columnId).toBe("duration");
    expect(result.current.sort.direction).toBe("asc");
  });

  it("setFilters merges partial updates", () => {
    const { result } = renderHook(() => useTaskTableState());
    act(() => result.current.setFilters({ warningsOnly: true }));
    expect(result.current.filters.warningsOnly).toBe(true);
    act(() => result.current.setFilters({ search: "x" }));
    expect(result.current.filters.warningsOnly).toBe(true);
    expect(result.current.filters.search).toBe("x");
  });

  it("resetFilters returns to defaults", () => {
    const { result } = renderHook(() => useTaskTableState());
    act(() => result.current.setFilters({ warningsOnly: true, search: "x" }));
    act(() => result.current.resetFilters());
    expect(result.current.filters).toEqual(DEFAULT_FILTERS);
  });
});
