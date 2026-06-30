/**
 * Minimal selection toolbar — prev / next / clear + a live label.
 */

import { memo, useMemo } from "react";
import { cn } from "@/lib/cn";
import type { TimelineSelectionController } from "@/dashboard/timeline/selection/TimelineSelectionController";
import { describeSelectionState } from "@/dashboard/timeline/selection/TimelineSelectionAccessibility";
import { DEFAULT_SELECTION_SHORTCUTS } from "@/dashboard/timeline/selection/TimelineSelectionShortcuts";
import type { TimelineSelectionState } from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

export interface TimelineSelectionToolbarProps {
  controller: TimelineSelectionController | null;
  state: TimelineSelectionState | null;
  className?: string;
}

function SelectionButton({
  label,
  onClick,
  disabled,
  ariaLabel,
  description,
  shortcut,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  ariaLabel: string;
  /** Verbose, action-first tooltip body. Prepended before the shortcut. */
  description?: string;
  shortcut?: string;
}) {
  const tooltipBody = description ?? ariaLabel;
  const title = shortcut ? `${tooltipBody} (${shortcut})` : tooltipBody;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      title={title}
      className={cn(
        "rounded border border-line bg-canvas px-2 py-1 font-mono text-xs text-text",
        "hover:border-accent hover:text-accent",
        "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line disabled:hover:text-text",
      )}
      data-selection-button={ariaLabel}
    >
      {label}
    </button>
  );
}

function TimelineSelectionToolbarImpl({
  controller,
  state,
  className,
}: TimelineSelectionToolbarProps) {
  const shortcuts = useMemo(() => {
    const out: Record<string, string> = {};
    for (const binding of DEFAULT_SELECTION_SHORTCUTS) {
      if (!out[binding.action]) out[binding.action] = binding.label;
    }
    return out;
  }, []);

  if (controller === null || state === null) {
    return (
      <div
        data-timeline-selection-toolbar="true"
        className={cn("flex items-center gap-2 px-3 py-1 text-xs text-muted", className)}
      >
        <span className="font-mono">Selection controls unavailable</span>
      </div>
    );
  }

  const hasSelection = state.selectedTaskId !== null;
  return (
    <div
      data-timeline-selection-toolbar="true"
      role="toolbar"
      aria-label="Timeline selection controls"
      className={cn("flex items-center gap-2 px-3 py-1 text-xs text-text", className)}
    >
      <SelectionButton
        label="↑"
        onClick={() => controller.selectPrevious()}
        ariaLabel="Select previous row"
        description="Select the previous task row"
        shortcut={shortcuts["select-previous"]}
        disabled={state.rowCount === 0 || (hasSelection && state.atFirst)}
      />
      <SelectionButton
        label="↓"
        onClick={() => controller.selectNext()}
        ariaLabel="Select next row"
        description="Select the next task row"
        shortcut={shortcuts["select-next"]}
        disabled={state.rowCount === 0 || (hasSelection && state.atLast)}
      />
      <SelectionButton
        label="⌂"
        onClick={() => controller.centerOnSelection()}
        ariaLabel="Center on selection"
        description="Center the timeline on the selected task"
        shortcut={shortcuts["center-selection"]}
        disabled={!hasSelection}
      />
      <SelectionButton
        label="✕"
        onClick={() => controller.clearSelection("programmatic")}
        ariaLabel="Clear selection"
        description="Clear the current task selection"
        shortcut={shortcuts["clear-selection"]}
        disabled={!hasSelection}
      />
      <output
        aria-live="polite"
        data-selection-label="true"
        className="ml-auto truncate font-mono tabular-nums text-[10px] uppercase tracking-widest text-muted"
      >
        {describeSelectionState(state)}
      </output>
    </div>
  );
}

export const TimelineSelectionToolbar = memo(TimelineSelectionToolbarImpl);
