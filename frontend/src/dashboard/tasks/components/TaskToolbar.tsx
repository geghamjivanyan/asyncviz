/**
 * Top-of-table toolbar.
 *
 * Hosts the search input + foundational filter toggles (active-only,
 * warnings-only, hide-terminal). The toolbar is intentionally
 * minimal — advanced filter UI can be added without changing the
 * underlying filter state shape.
 */

import type { ChangeEvent } from "react";
import { cn } from "@/lib/cn";
import type { TaskFilterState } from "@/dashboard/tasks/models/filters";

export interface TaskToolbarProps {
  filters: TaskFilterState;
  onFiltersChange: (next: Partial<TaskFilterState>) => void;
  totalRows: number;
  visibleRows: number;
  onResetFilters: () => void;
}

export function TaskToolbar({
  filters,
  onFiltersChange,
  totalRows,
  visibleRows,
  onResetFilters,
}: TaskToolbarProps) {
  const onSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({ search: event.target.value });
  };
  return (
    <div
      data-task-toolbar="true"
      className="flex h-9 shrink-0 items-center gap-3 border-b border-line bg-panel px-3 text-xs"
    >
      <label className="flex flex-1 items-center gap-2 text-subtle">
        <span className="text-[10px] uppercase tracking-widest text-muted">Search</span>
        <input
          type="search"
          value={filters.search}
          onChange={onSearchChange}
          placeholder="Filter by id, name, or coroutine…"
          aria-label="Filter tasks"
          className="flex-1 rounded border border-line bg-canvas px-2 py-0.5 font-mono text-text outline-none placeholder:text-subtle focus:border-accent"
        />
      </label>
      <ToggleButton
        active={filters.activeOnly}
        onClick={() => onFiltersChange({ activeOnly: !filters.activeOnly })}
        label="Active"
      />
      <ToggleButton
        active={filters.warningsOnly}
        onClick={() => onFiltersChange({ warningsOnly: !filters.warningsOnly })}
        label="Warnings"
      />
      <ToggleButton
        active={filters.hideTerminal}
        onClick={() => onFiltersChange({ hideTerminal: !filters.hideTerminal })}
        label="Hide terminal"
      />
      <button
        type="button"
        onClick={onResetFilters}
        className="rounded border border-line px-2 py-0.5 text-subtle hover:border-accent hover:text-accent"
      >
        Reset
      </button>
      <span className="font-mono text-subtle" aria-live="polite">
        {visibleRows}/{totalRows}
      </span>
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded border px-2 py-0.5 font-mono text-xs uppercase tracking-widest",
        active
          ? "border-accent text-accent"
          : "border-line text-subtle hover:border-accent hover:text-accent",
      )}
    >
      {label}
    </button>
  );
}
