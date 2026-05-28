/**
 * Scrollable list of event rows, optionally grouped.
 *
 * Today every row inside the virtualization window renders; the
 * architecture is windowing-ready (stable heights, dedicated scroll
 * container, single source for the visible set).
 */

import { useCallback, useState } from "react";
import { EmptyState } from "@/ui/feedback/EmptyState";
import { RuntimeEventRow } from "@/dashboard/events/components/RuntimeEventRow";
import { useEventVirtualization } from "@/dashboard/events/hooks/useEventVirtualization";
import type { EventGroup } from "@/dashboard/events/utils/grouping";

export interface RuntimeEventListProps {
  groups: readonly EventGroup[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  emptyTitle?: string;
  emptyDescription?: string;
}

export function RuntimeEventList({
  groups,
  selectedTaskId,
  onSelectTask,
  emptyTitle = "No events",
  emptyDescription = "Events will appear here as the runtime emits lifecycle frames.",
}: RuntimeEventListProps) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set());

  const handleToggle = useCallback((eventId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  }, []);

  const totalRows = groups.reduce((acc, g) => acc + g.rows.length, 0);
  if (totalRows === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <ol
      role="feed"
      aria-busy="false"
      aria-label="Runtime event feed"
      data-event-feed="true"
      className="flex w-full flex-col"
    >
      {groups.map((group) => (
        <EventGroupSection
          key={group.groupId}
          group={group}
          selectedTaskId={selectedTaskId}
          expanded={expanded}
          onSelectTask={onSelectTask}
          onToggle={handleToggle}
        />
      ))}
    </ol>
  );
}

function EventGroupSection({
  group,
  selectedTaskId,
  expanded,
  onSelectTask,
  onToggle,
}: {
  group: EventGroup;
  selectedTaskId: string | null;
  expanded: ReadonlySet<string>;
  onSelectTask: (taskId: string) => void;
  onToggle: (eventId: string) => void;
}) {
  const rows = useEventVirtualization(group.rows);
  return (
    <li role="group" aria-label={group.label} data-event-group={group.groupId}>
      {group.mode !== "none" && (
        <div className="sticky top-0 z-10 flex items-center gap-2 border-y border-line bg-panel px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-muted">
          <span>{group.label}</span>
          <span className="ml-auto tabular-nums text-subtle">{group.rows.length}</span>
        </div>
      )}
      <ul className="flex flex-col">
        {rows.visibleRows.map((row) => (
          <RuntimeEventRow
            key={row.rowKey}
            row={row}
            selected={row.taskId === selectedTaskId}
            expanded={expanded.has(row.eventId)}
            onSelect={onSelectTask}
            onToggleExpanded={onToggle}
          />
        ))}
      </ul>
    </li>
  );
}
