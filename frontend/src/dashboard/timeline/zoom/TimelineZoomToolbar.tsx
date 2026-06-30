/**
 * Minimal zoom toolbar — a row of buttons + the current zoom label.
 *
 * The toolbar is intentionally plain: it speaks only the canonical
 * :class:`TimelineZoomController` API. Visual treatments belong to
 * the dashboard layout.
 */

import { memo, useMemo } from "react";
import { cn } from "@/lib/cn";
import type { TimelineZoomController } from "@/dashboard/timeline/zoom/TimelineZoomController";
import { describeZoomState } from "@/dashboard/timeline/zoom/TimelineZoomAccessibility";
import { DEFAULT_ZOOM_SHORTCUTS } from "@/dashboard/timeline/zoom/TimelineZoomShortcuts";
import type {
  TimelineZoomState,
  ZoomPreset,
} from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

export interface TimelineZoomToolbarProps {
  controller: TimelineZoomController | null;
  state: TimelineZoomState | null;
  /** Range used by the "Fit all" button. */
  fitAll?: { startSeconds: number; endSeconds: number } | null;
  /** Optional preset list rendered as additional buttons. */
  presets?: readonly ZoomPreset[];
  className?: string;
}

function ZoomButton({
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
      data-zoom-button={ariaLabel}
    >
      {label}
    </button>
  );
}

function TimelineZoomToolbarImpl({
  controller,
  state,
  fitAll,
  presets,
  className,
}: TimelineZoomToolbarProps) {
  const shortcuts = useMemo(() => {
    const out: Record<string, string> = {};
    for (const binding of DEFAULT_ZOOM_SHORTCUTS) {
      if (!out[binding.action]) out[binding.action] = binding.label;
    }
    return out;
  }, []);

  if (controller === null || state === null) {
    return (
      <div
        data-timeline-zoom-toolbar="true"
        className={cn(
          "flex items-center gap-2 px-3 py-1 text-xs text-muted",
          className,
        )}
      >
        <span className="font-mono">Zoom controls unavailable</span>
      </div>
    );
  }

  return (
    <div
      data-timeline-zoom-toolbar="true"
      role="toolbar"
      aria-label="Timeline zoom controls"
      className={cn("flex items-center gap-2 px-3 py-1 text-xs text-text", className)}
    >
      <ZoomButton
        label="−"
        onClick={() => controller.zoomOut()}
        disabled={state.atMax}
        ariaLabel="Zoom out"
        description="Zoom out — show a wider time range"
        shortcut={shortcuts["zoom-out"]}
      />
      <ZoomButton
        label="+"
        onClick={() => controller.zoomIn()}
        disabled={state.atMin}
        ariaLabel="Zoom in"
        description="Zoom in — focus on a narrower time range"
        shortcut={shortcuts["zoom-in"]}
      />
      {fitAll ? (
        <ZoomButton
          label="Fit"
          onClick={() => controller.zoomToRange(fitAll.startSeconds, fitAll.endSeconds, "fit-all")}
          ariaLabel="Fit timeline to data"
          description="Fit the visible window to all recorded task activity"
          shortcut={shortcuts["fit-all"]}
        />
      ) : null}
      {fitAll ? (
        <ZoomButton
          label="Reset"
          onClick={() => controller.zoomToRange(fitAll.startSeconds, fitAll.endSeconds, "fit-default")}
          ariaLabel="Reset zoom"
          description="Reset the zoom level to the default view"
          shortcut={shortcuts["zoom-reset"]}
        />
      ) : null}
      {presets && presets.length > 0 ? (
        <div className="flex items-center gap-1 border-l border-line pl-2">
          {presets.map((preset) => (
            <ZoomButton
              key={preset.kind}
              label={preset.label ?? preset.kind}
              onClick={() => controller.activatePreset(preset)}
              ariaLabel={`Preset ${preset.kind}`}
              description={`Apply zoom preset: ${preset.label ?? preset.kind}`}
            />
          ))}
        </div>
      ) : null}
      <output
        aria-live="polite"
        data-zoom-label="true"
        className="ml-auto font-mono tabular-nums text-[10px] uppercase tracking-widest text-muted"
      >
        {describeZoomState(state)}
      </output>
    </div>
  );
}

export const TimelineZoomToolbar = memo(TimelineZoomToolbarImpl);
