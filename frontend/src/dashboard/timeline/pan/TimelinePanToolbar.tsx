/**
 * Minimal pan toolbar — left / right step buttons + a "fit start" /
 * "fit end" pair.
 */

import { memo, useMemo } from "react";
import { cn } from "@/lib/cn";
import type { TimelinePanController } from "@/dashboard/timeline/pan/TimelinePanController";
import { describePanState } from "@/dashboard/timeline/pan/TimelinePanAccessibility";
import { DEFAULT_PAN_SHORTCUTS } from "@/dashboard/timeline/pan/TimelinePanShortcuts";
import type { TimelinePanState } from "@/dashboard/timeline/pan/models/TimelinePanModels";

export interface TimelinePanToolbarProps {
  controller: TimelinePanController | null;
  state: TimelinePanState | null;
  /** Range used by the Home/End controls. */
  dataRange?: { startSeconds: number; endSeconds: number } | null;
  className?: string;
}

function PanButton({
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
      data-pan-button={ariaLabel}
    >
      {label}
    </button>
  );
}

function TimelinePanToolbarImpl({
  controller,
  state,
  dataRange,
  className,
}: TimelinePanToolbarProps) {
  const shortcuts = useMemo(() => {
    const out: Record<string, string> = {};
    for (const binding of DEFAULT_PAN_SHORTCUTS) {
      if (!out[binding.action]) out[binding.action] = binding.label;
    }
    return out;
  }, []);

  if (controller === null || state === null) {
    return (
      <div
        data-timeline-pan-toolbar="true"
        className={cn("flex items-center gap-2 px-3 py-1 text-xs text-muted", className)}
      >
        <span className="font-mono">Pan controls unavailable</span>
      </div>
    );
  }

  const onHome = (): void => {
    if (dataRange) controller.panToTime(dataRange.startSeconds);
  };
  const onEnd = (): void => {
    if (dataRange) {
      controller.panToTime(dataRange.endSeconds - state.durationSeconds);
    }
  };

  return (
    <div
      data-timeline-pan-toolbar="true"
      role="toolbar"
      aria-label="Timeline pan controls"
      className={cn("flex items-center gap-2 px-3 py-1 text-xs text-text", className)}
    >
      {dataRange ? (
        <PanButton
          label="⏮"
          onClick={onHome}
          ariaLabel="Pan to start"
          description="Jump to the earliest recorded event"
          shortcut={shortcuts["pan-home"]}
          disabled={state.atMinTime}
        />
      ) : null}
      <PanButton
        label="◀"
        onClick={() => controller.panLeft()}
        ariaLabel="Pan left"
        description="Pan left — show earlier events"
        shortcut={shortcuts["pan-left"]}
        disabled={state.atMinTime}
      />
      <PanButton
        label="▶"
        onClick={() => controller.panRight()}
        ariaLabel="Pan right"
        description="Pan right — show later events"
        shortcut={shortcuts["pan-right"]}
        disabled={state.atMaxTime}
      />
      {dataRange ? (
        <PanButton
          label="⏭"
          onClick={onEnd}
          ariaLabel="Pan to end"
          description="Jump to the latest recorded event"
          shortcut={shortcuts["pan-end"]}
          disabled={state.atMaxTime}
        />
      ) : null}
      <output
        aria-live="polite"
        data-pan-label="true"
        className="ml-auto font-mono tabular-nums text-[10px] uppercase tracking-widest text-muted"
      >
        {describePanState(state)}
      </output>
    </div>
  );
}

export const TimelinePanToolbar = memo(TimelinePanToolbarImpl);
