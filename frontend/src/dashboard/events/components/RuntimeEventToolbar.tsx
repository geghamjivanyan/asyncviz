/**
 * Top-of-feed toolbar — search + filter toggles + grouping + sort.
 */

import { RuntimeEventSearch } from "@/dashboard/events/components/RuntimeEventSearch";
import { RuntimeEventFilter } from "@/dashboard/events/components/RuntimeEventFilter";
import { RuntimeEventGrouping } from "@/dashboard/events/components/RuntimeEventGrouping";
import type {
  EventFilterState,
  EventGroupingState,
  EventSortState,
} from "@/dashboard/events/models/filters";

export interface RuntimeEventToolbarProps {
  filters: EventFilterState;
  sort: EventSortState;
  grouping: EventGroupingState;
  totalRows: number;
  visibleRows: number;
  onFiltersChange: (next: Partial<EventFilterState>) => void;
  onResetFilters: () => void;
  onToggleSort: () => void;
  onGroupingChange: (mode: EventGroupingState["mode"]) => void;
  onClear?: () => void;
}

export function RuntimeEventToolbar({
  filters,
  sort,
  grouping,
  totalRows,
  visibleRows,
  onFiltersChange,
  onResetFilters,
  onToggleSort,
  onGroupingChange,
  onClear,
}: RuntimeEventToolbarProps) {
  return (
    <div
      role="toolbar"
      aria-label="Event feed controls"
      data-event-toolbar="true"
      className="flex h-9 shrink-0 flex-wrap items-center gap-3 border-b border-line bg-panel px-3 text-xs"
    >
      <RuntimeEventSearch
        value={filters.search}
        onChange={(search) => onFiltersChange({ search })}
      />
      <RuntimeEventFilter
        warningsOnly={filters.warningsOnly}
        replayOnly={filters.replayOnly}
        terminalOnly={filters.terminalOnly}
        activeTimelineOnly={filters.activeTimelineOnly}
        onChange={onFiltersChange}
      />
      <RuntimeEventGrouping mode={grouping.mode} onChange={onGroupingChange} />
      <button
        type="button"
        onClick={onToggleSort}
        aria-label={`Sort ${sort.direction === "newest" ? "newest first" : "oldest first"}`}
        className="rounded border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
      >
        {sort.direction === "newest" ? "Newest" : "Oldest"} ▾
      </button>
      <button
        type="button"
        onClick={onResetFilters}
        className="rounded border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
      >
        Reset
      </button>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="rounded border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
        >
          Clear
        </button>
      )}
      <span className="ml-auto font-mono text-xs text-subtle" aria-live="polite">
        {visibleRows}/{totalRows}
      </span>
    </div>
  );
}
