/**
 * Filter chip bar.
 *
 * Four mutually-exclusive modes today: ``all`` / ``active`` /
 * ``recovered`` / ``freeze-only``. The bar is a `radiogroup` so
 * screen readers announce the change cleanly.
 *
 * The freeze-only chip is a convenience over the future generic
 * severity multi-selector. When operators request the full multi-
 * selector we can swap the bar without changing consumers because
 * the underlying filter type already supports multiple severities.
 */

import { memo, useCallback } from "react";
import { cn } from "@/lib/cn";
import type { BlockingWarningFilterMode } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { recordBlockingWarningTrace } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";
import { getBlockingWarningPanelMetrics } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";

interface FilterChip {
  mode: BlockingWarningFilterMode;
  label: string;
}

const CHIPS: readonly FilterChip[] = [
  { mode: "all", label: "All" },
  { mode: "active", label: "Active" },
  { mode: "recovered", label: "Recovered" },
  { mode: "freeze-only", label: "Freezes" },
];

export interface BlockingWarningFiltersProps {
  mode: BlockingWarningFilterMode;
  onChange: (mode: BlockingWarningFilterMode) => void;
  className?: string;
}

function BlockingWarningFiltersImpl({ mode, onChange, className }: BlockingWarningFiltersProps) {
  const handleChange = useCallback(
    (next: BlockingWarningFilterMode) => {
      if (next === mode) return;
      onChange(next);
      getBlockingWarningPanelMetrics().recordFilterChange();
      recordBlockingWarningTrace({ kind: "filter-changed", detail: next });
    },
    [mode, onChange],
  );

  return (
    <div
      role="radiogroup"
      aria-label="Blocking warning filter"
      data-testid="blocking-warning-filters"
      className={cn("flex flex-wrap gap-1", className)}
    >
      {CHIPS.map((chip) => {
        const active = chip.mode === mode;
        return (
          <button
            key={chip.mode}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => handleChange(chip.mode)}
            className={cn(
              "rounded border px-2 py-0.5 font-mono text-xs uppercase tracking-wider",
              active
                ? "border-accent bg-accent/10 text-accent"
                : "border-line bg-elevated text-subtle hover:border-accent hover:text-accent",
            )}
            data-testid={`blocking-warning-filter-${chip.mode}`}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}

export const BlockingWarningFilters = memo(BlockingWarningFiltersImpl);
