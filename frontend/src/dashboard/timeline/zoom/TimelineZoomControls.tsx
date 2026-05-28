/**
 * Higher-level zoom controls wrapper — composes the toolbar with a
 * hidden accessibility live region that announces zoom-state
 * changes to assistive tooling.
 */

import { memo } from "react";
import {
  TimelineZoomToolbar,
  type TimelineZoomToolbarProps,
} from "@/dashboard/timeline/zoom/TimelineZoomToolbar";
import { describeZoomState } from "@/dashboard/timeline/zoom/TimelineZoomAccessibility";

export interface TimelineZoomControlsProps extends TimelineZoomToolbarProps {
  /** Hide the toolbar visually but keep the a11y companion. */
  hidden?: boolean;
}

function TimelineZoomControlsImpl({ hidden, ...toolbarProps }: TimelineZoomControlsProps) {
  return (
    <div data-timeline-zoom-controls="true" className={hidden ? "sr-only" : undefined}>
      <TimelineZoomToolbar {...toolbarProps} />
      <p role="status" aria-live="polite" className="sr-only" data-zoom-announcement="true">
        {toolbarProps.state ? describeZoomState(toolbarProps.state) : "Zoom controls unavailable."}
      </p>
    </div>
  );
}

export const TimelineZoomControls = memo(TimelineZoomControlsImpl);
