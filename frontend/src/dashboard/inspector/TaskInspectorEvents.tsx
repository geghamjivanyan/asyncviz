/**
 * Events panel — surfaces recent runtime events scoped to the
 * selected task.
 */

import { memo } from "react";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";

export interface TaskInspectorEventsProps {
  events: ReadonlyArray<{
    event_id: string;
    event_type: string;
    monotonic_ns: number;
    task_id: string;
  }>;
  className?: string;
}

function TaskInspectorEventsImpl({ events, className }: TaskInspectorEventsProps) {
  return (
    <Card
      data-inspector-panel="events"
      padding="sm"
      className={cn("flex flex-col gap-2", className)}
    >
      <header>
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Events</h3>
      </header>
      {events.length === 0 ? (
        <p className="text-[11px] text-subtle">No recent events for this task.</p>
      ) : (
        <ul className="flex max-h-48 flex-col gap-1 overflow-auto font-mono text-[11px]">
          {events
            .slice()
            .reverse()
            .map((event) => (
              <li
                key={event.event_id}
                data-event-id={event.event_id}
                className="flex justify-between gap-2"
              >
                <span className="truncate text-text">{event.event_type}</span>
                <span className="tabular-nums text-subtle">
                  {(event.monotonic_ns / 1e9).toFixed(3)}s
                </span>
              </li>
            ))}
        </ul>
      )}
    </Card>
  );
}

export const TaskInspectorEvents = memo(TaskInspectorEventsImpl);
