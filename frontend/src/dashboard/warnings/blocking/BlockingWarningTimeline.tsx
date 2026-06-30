/**
 * Inline escalation timeline.
 *
 * Renders one row per :type:`BlockingEscalationEntry`. The escalation
 * history is bounded server-side (16 entries) so an unbounded list
 * here is fine — no virtualization yet, just a static list.
 *
 * Future task: switch to a horizontal sparkline that maps each
 * escalation onto the larger timeline canvas. For now the textual
 * list keeps the wire-shape readable + screen-reader friendly.
 */

import { memo } from "react";
import type { BlockingWarningView } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { formatDurationMs } from "@/dashboard/warnings/blocking/utils/formatting";

export interface BlockingWarningTimelineProps {
  view: BlockingWarningView;
  className?: string;
}

function BlockingWarningTimelineImpl({ view, className }: BlockingWarningTimelineProps) {
  if (view.escalationHistory.length === 0) {
    return (
      <p className={className} data-testid="blocking-warning-timeline-empty">
        <span className="text-subtle text-xs">No escalations recorded.</span>
      </p>
    );
  }

  return (
    <ol
      className={className}
      aria-label="Escalation history"
      data-testid="blocking-warning-timeline"
    >
      {view.escalationHistory.map((entry, index) => {
        const fromFirstMs = (entry.monotonic_ns - view.firstSeenNs) / 1_000_000;
        return (
          <li
            key={`${entry.monotonic_ns}-${index}`}
            className="flex items-center gap-2 py-0.5 text-xs font-mono"
          >
            <span className="text-subtle">+{formatDurationMs(Math.max(0, fromFirstMs))}</span>
            <span className="text-text">
              {entry.from_severity} → {entry.to_severity}
            </span>
            {entry.sample_index !== null && (
              <span className="text-subtle">sample #{entry.sample_index}</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export const BlockingWarningTimeline = memo(BlockingWarningTimelineImpl);
