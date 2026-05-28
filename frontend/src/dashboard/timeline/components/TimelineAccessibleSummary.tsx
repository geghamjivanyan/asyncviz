/**
 * Parallel accessibility companion for the canvas timeline.
 *
 * Canvas is not screen-reader-accessible on its own. This component
 * renders a hidden ``aria`` list of visible tasks + segment counts so
 * assistive tooling can still navigate the runtime.
 *
 * The companion is purely metadata — it never tries to mirror visual
 * geometry. Screen-reader users get a coherent semantic list of the
 * currently visible rows.
 */

import { memo } from "react";
import type { TimelineProjection } from "@/dashboard/timeline/selectors/projectTimeline";
import type { TimelineViewportWindowSnapshot } from "@/dashboard/timeline/virtualization";
import type { TimelineTimeScale } from "@/dashboard/timeline/scaling";

export interface TimelineAccessibleSummaryProps {
  projection: TimelineProjection;
  selectedTaskId: string | null;
  /** Currently-resolved virtualization window — surfaces visible-row
   *  ranges in the parallel a11y companion. */
  visibleWindow?: TimelineViewportWindowSnapshot | null;
  /** Active time scale — surfaces visible-time + pixels-per-second so
   *  assistive tooling can announce the zoom level. */
  timeScale?: TimelineTimeScale | null;
}

function TimelineAccessibleSummaryImpl({
  projection,
  selectedTaskId,
  visibleWindow,
  timeScale,
}: TimelineAccessibleSummaryProps) {
  if (projection.rows.length === 0) {
    return (
      <p className="sr-only" role="status">
        Timeline is empty — no tasks tracked yet.
      </p>
    );
  }
  return (
    <section
      data-timeline-a11y="true"
      aria-label="Timeline summary"
      className="sr-only"
      data-window-row-start={visibleWindow?.rows.startIndex ?? undefined}
      data-window-row-end={visibleWindow?.rows.endIndex ?? undefined}
      data-window-time-start={visibleWindow?.time.startSeconds ?? undefined}
      data-window-time-end={visibleWindow?.time.endSeconds ?? undefined}
    >
      <p>
        {projection.rows.length} task row{projection.rows.length === 1 ? "" : "s"} visible.
      </p>
      {visibleWindow !== undefined && visibleWindow !== null ? (
        <p>
          Window rows {visibleWindow.rows.startIndex}–{visibleWindow.rows.endIndex} of{" "}
          {visibleWindow.rows.totalRows}; time {visibleWindow.time.startSeconds.toFixed(2)}–
          {visibleWindow.time.endSeconds.toFixed(2)}s.
        </p>
      ) : null}
      {timeScale !== undefined && timeScale !== null ? (
        <p data-scale-duration={timeScale.durationSeconds}>
          Scale {timeScale.durationSeconds.toFixed(3)}s across{" "}
          {Math.round(timeScale.widthPx)}px ({timeScale.pixelsPerSecond.toFixed(2)} px/s).
        </p>
      ) : null}
      <ul role="list">
        {projection.rows.map((row) => {
          const segmentsForRow = projection.segments.filter(
            (s) => s.rowIndex === row.rowIndex,
          );
          const segmentCount = segmentsForRow.length;
          const activeCount = segmentsForRow.filter((s) => s.isActive).length;
          const lifecycleSummary = summarizeLifecycle(segmentsForRow);
          const selected = row.taskId === selectedTaskId;
          const warningSummary =
            row.warningSeverity !== undefined && row.warningSeverity !== null
              ? `, ${row.warningCount ?? 0} ${row.warningSeverity} warning${(row.warningCount ?? 0) === 1 ? "" : "s"}`
              : "";
          return (
            <li
              key={row.taskId}
              role="listitem"
              data-task-id={row.taskId}
              data-row-state={row.state ?? "unknown"}
              data-row-warning={row.warningSeverity ?? "none"}
              data-segment-count={segmentCount}
              data-active-segments={activeCount}
              data-lifecycle-mix={lifecycleSummary}
              aria-current={selected ? "true" : undefined}
            >
              {row.label}
              {row.coroutineName && row.coroutineName !== row.label
                ? ` (${row.coroutineName})`
                : ""}
              : {row.state ?? "unknown"} · {segmentCount} segment
              {segmentCount === 1 ? "" : "s"}
              {activeCount > 0 ? ` (${activeCount} active)` : ""}
              {lifecycleSummary ? ` — ${lifecycleSummary}` : ""}
              {warningSummary}
              {selected ? " (selected)" : ""}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function summarizeLifecycle(
  segments: ReadonlyArray<{ lifecycleState?: string; intent?: string }>,
): string {
  if (segments.length === 0) return "";
  const counts = new Map<string, number>();
  for (const seg of segments) {
    const key = seg.lifecycleState ?? seg.intent ?? "unknown";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => `${key}:${count}`)
    .join(", ");
}

export const TimelineAccessibleSummary = memo(TimelineAccessibleSummaryImpl);
