/**
 * One row in the runtime event feed.
 *
 * Wrapped in :func:`React.memo` with a custom comparator: the row
 * re-renders only when its signature changes, or its selection /
 * collapse state changes. The signature catches every visible change
 * so realtime updates flow naturally without rerendering siblings.
 */

import { memo, useCallback, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";
import { RuntimeEventBadge } from "@/dashboard/events/components/RuntimeEventBadge";
import { RuntimeEventTimestamp } from "@/dashboard/events/components/RuntimeEventTimestamp";
import { RuntimeEventMetadata } from "@/dashboard/events/components/RuntimeEventMetadata";
import { formatTaskIdCompact } from "@/dashboard/events/utils/format";
import type { EventRow } from "@/dashboard/events/models/eventRow";
import { getEventFeedMetrics } from "@/dashboard/events/observability";

const DOT_COLOR: Record<EventRow["intent"], string> = {
  default: "bg-line",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};

export interface RuntimeEventRowProps {
  row: EventRow;
  selected: boolean;
  expanded: boolean;
  onSelect: (taskId: string) => void;
  onToggleExpanded: (eventId: string) => void;
  style?: React.CSSProperties;
}

function RuntimeEventRowImpl({
  row,
  selected,
  expanded,
  onSelect,
  onToggleExpanded,
  style,
}: RuntimeEventRowProps) {
  getEventFeedMetrics().recordRowRender();

  const handleSelect = useCallback(() => {
    onSelect(row.taskId);
  }, [onSelect, row.taskId]);

  const handleToggle = useCallback(() => {
    onToggleExpanded(row.eventId);
  }, [onToggleExpanded, row.eventId]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLLIElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        onSelect(row.taskId);
      } else if (event.key === " ") {
        event.preventDefault();
        onToggleExpanded(row.eventId);
      }
    },
    [onSelect, onToggleExpanded, row.taskId, row.eventId],
  );

  const taskLabel = formatTaskIdCompact(row.taskId);
  const failureReason = row.exceptionType
    ? `${row.exceptionType}${row.exceptionMessage ? `: ${row.exceptionMessage}` : ""}`
    : null;
  const cancellation = row.cancellationOrigin ? `cancelled · ${row.cancellationOrigin}` : null;

  return (
    <li
      role="article"
      aria-selected={selected}
      aria-expanded={expanded}
      data-event-id={row.eventId}
      data-event-category={row.category}
      data-event-source={row.source}
      data-replay={row.source === "replay" ? "true" : undefined}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      style={style}
      className={cn(
        "flex w-full cursor-default flex-col gap-1 border-b border-line/40 px-3 py-1.5 outline-none",
        "focus-visible:ring-1 focus-visible:ring-accent",
        selected ? "bg-elevated text-text" : "text-muted hover:bg-elevated/40",
      )}
    >
      <div className="flex w-full items-center gap-2">
        <span
          aria-hidden="true"
          data-event-dot="true"
          className={cn("inline-flex h-1.5 w-1.5 shrink-0 rounded-full", DOT_COLOR[row.intent])}
        />
        <button
          type="button"
          onClick={handleSelect}
          aria-label={`Select task ${row.taskId}`}
          className="flex min-w-0 flex-1 items-center gap-2 rounded text-left hover:text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
        >
          <RuntimeEventBadge category={row.category} intent={row.intent} />
          <span className="truncate font-mono text-xs text-text" title={row.label}>
            {row.label}
          </span>
          <span className="truncate font-mono text-[10px] text-subtle">{taskLabel}</span>
        </button>
        {row.warnings.count > 0 && (
          <span
            data-warning-count="true"
            aria-label={`${row.warnings.count} active warning${row.warnings.count === 1 ? "" : "s"}`}
            className={cn(
              "shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest",
              row.warnings.highestSeverity === "critical" ||
                row.warnings.highestSeverity === "error"
                ? "border-danger text-danger"
                : "border-warning text-warning",
            )}
          >
            {row.warnings.count}
          </span>
        )}
        {row.source === "replay" && (
          <span
            aria-label="replay"
            className="shrink-0 rounded border border-accent px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-accent"
          >
            replay
          </span>
        )}
        <button
          type="button"
          onClick={handleToggle}
          aria-expanded={expanded}
          aria-label={expanded ? "Collapse event details" : "Expand event details"}
          className="shrink-0 rounded border border-line px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
        >
          {expanded ? "−" : "+"}
        </button>
        <RuntimeEventTimestamp
          timestampSeconds={row.timestamp}
          durationSeconds={row.durationSeconds}
        />
      </div>
      {expanded && (
        <div className="ml-3 flex flex-col gap-1 border-l border-line/40 pl-3 font-mono text-[11px]">
          <dl className="flex flex-wrap gap-x-3 gap-y-0.5 text-subtle">
            <span className="inline-flex items-center gap-1">
              <dt className="text-muted">event</dt>
              <dd className="text-text">{row.eventType}</dd>
            </span>
            <span className="inline-flex items-center gap-1">
              <dt className="text-muted">seq</dt>
              <dd className="text-text">{row.sequence ?? "—"}</dd>
            </span>
            <span className="inline-flex items-center gap-1">
              <dt className="text-muted">task</dt>
              <dd className="text-text">{row.taskId}</dd>
            </span>
            {row.parentTaskId && (
              <span className="inline-flex items-center gap-1">
                <dt className="text-muted">parent</dt>
                <dd className="text-text">{row.parentTaskId}</dd>
              </span>
            )}
            {row.coroutineName && (
              <span className="inline-flex items-center gap-1">
                <dt className="text-muted">coroutine</dt>
                <dd className="text-text">{row.coroutineName}</dd>
              </span>
            )}
          </dl>
          {failureReason && <p className="text-danger">{failureReason}</p>}
          {cancellation && <p className="text-warning">{cancellation}</p>}
          <RuntimeEventMetadata entries={row.metadata} />
        </div>
      )}
    </li>
  );
}

function rowEqual(prev: RuntimeEventRowProps, next: RuntimeEventRowProps): boolean {
  if (prev.row.signature !== next.row.signature) return false;
  if (prev.selected !== next.selected) return false;
  if (prev.expanded !== next.expanded) return false;
  if (prev.onSelect !== next.onSelect) return false;
  if (prev.onToggleExpanded !== next.onToggleExpanded) return false;
  if (prev.style !== next.style) return false;
  return true;
}

export const RuntimeEventRow = memo(RuntimeEventRowImpl, rowEqual);
