/**
 * Store-aware wrapper for the runtime event feed.
 *
 * The container is the only piece that reaches into the canonical
 * Zustand store + the feed-local state. Everything below it (rows,
 * toolbar, list) is pure data → JSX.
 */

import { useCallback } from "react";
import { useRuntimeStore } from "@/state/runtime/store";
import { useSelectedTaskId } from "@/state/runtime/selectors";
import { RuntimeEventFeed } from "@/dashboard/events/components/RuntimeEventFeed";
import { useEventFeedState } from "@/dashboard/events/hooks/useEventFeedState";
import { useEventRows } from "@/dashboard/events/hooks/useEventRows";
import { useEventGroups } from "@/dashboard/events/hooks/useEventGroups";
import { useProjectedEventRows } from "@/dashboard/events/selectors/storeSelectors";
import type { EventGroupingMode } from "@/dashboard/events/models/filters";

export interface RuntimeEventFeedContainerProps {
  className?: string;
}

export function RuntimeEventFeedContainer({ className }: RuntimeEventFeedContainerProps) {
  const { filters, sort, grouping, setFilters, resetFilters, toggleSort, setGrouping } =
    useEventFeedState();

  const projected = useProjectedEventRows();
  const rows = useEventRows(filters, sort);
  const groups = useEventGroups(rows, grouping);

  const selectedTaskId = useSelectedTaskId();
  const storeSelect = useRuntimeStore((s) => s.selectTask);
  const clearEvents = useRuntimeStore((s) => s.clearEvents);
  const onSelectTask = useCallback((taskId: string) => storeSelect(taskId), [storeSelect]);
  const onGroupingChange = useCallback(
    (mode: EventGroupingMode) => setGrouping({ mode }),
    [setGrouping],
  );

  return (
    <RuntimeEventFeed
      groups={groups}
      totalRows={projected.length}
      visibleRows={rows.length}
      selectedTaskId={selectedTaskId}
      onSelectTask={onSelectTask}
      filters={filters}
      sort={sort}
      grouping={grouping}
      onFiltersChange={setFilters}
      onResetFilters={resetFilters}
      onToggleSort={toggleSort}
      onGroupingChange={onGroupingChange}
      onClear={clearEvents}
      className={className}
    />
  );
}
