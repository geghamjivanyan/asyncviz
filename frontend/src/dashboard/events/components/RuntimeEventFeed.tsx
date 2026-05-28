/**
 * Canonical runtime event feed.
 *
 * Composes the toolbar + the grouped event list inside a single
 * accessible ``role="region"`` container. The component is
 * consumer-friendly: callers pass already-projected rows + state
 * objects, the feed just renders. The container component
 * :class:`RuntimeEventFeedContainer` does the store wiring.
 */

import { cn } from "@/lib/cn";
import { RuntimeEventList } from "@/dashboard/events/components/RuntimeEventList";
import { RuntimeEventToolbar } from "@/dashboard/events/components/RuntimeEventToolbar";
import type { EventGroup } from "@/dashboard/events/utils/grouping";
import type {
  EventFilterState,
  EventGroupingState,
  EventSortState,
} from "@/dashboard/events/models/filters";

export interface RuntimeEventFeedProps {
  groups: readonly EventGroup[];
  totalRows: number;
  visibleRows: number;
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  filters: EventFilterState;
  sort: EventSortState;
  grouping: EventGroupingState;
  onFiltersChange: (next: Partial<EventFilterState>) => void;
  onResetFilters: () => void;
  onToggleSort: () => void;
  onGroupingChange: (mode: EventGroupingState["mode"]) => void;
  onClear?: () => void;
  className?: string;
}

export function RuntimeEventFeed({
  groups,
  totalRows,
  visibleRows,
  selectedTaskId,
  onSelectTask,
  filters,
  sort,
  grouping,
  onFiltersChange,
  onResetFilters,
  onToggleSort,
  onGroupingChange,
  onClear,
  className,
}: RuntimeEventFeedProps) {
  return (
    <section
      role="region"
      aria-label="Runtime event feed"
      data-runtime-event-feed="true"
      className={cn("flex h-full min-h-0 min-w-0 flex-col", className)}
    >
      <RuntimeEventToolbar
        filters={filters}
        sort={sort}
        grouping={grouping}
        totalRows={totalRows}
        visibleRows={visibleRows}
        onFiltersChange={onFiltersChange}
        onResetFilters={onResetFilters}
        onToggleSort={onToggleSort}
        onGroupingChange={onGroupingChange}
        onClear={onClear}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto">
        <RuntimeEventList
          groups={groups}
          selectedTaskId={selectedTaskId}
          onSelectTask={onSelectTask}
        />
      </div>
    </section>
  );
}
