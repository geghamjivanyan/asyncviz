import { useEvents, useRuntimeStore } from "@/state/runtime";
import { cn } from "@/lib/cn";
import type { TaskLifecycleEvent } from "@/types/runtime";
import { PanelShell } from "./PanelShell";

const EVENT_COLOR: Record<string, string> = {
  "asyncio.task.created": "text-accent",
  "asyncio.task.started": "text-success",
  "asyncio.task.waiting": "text-warning",
  "asyncio.task.resumed": "text-success",
  "asyncio.task.completed": "text-muted",
  "asyncio.task.cancelled": "text-subtle",
  "asyncio.task.failed": "text-danger",
};

function eventDuration(event: TaskLifecycleEvent): number | null {
  if ("duration_seconds" in event && event.duration_seconds != null) {
    return event.duration_seconds;
  }
  return null;
}

function formatDuration(seconds: number): string {
  if (seconds < 0.001) return `${(seconds * 1_000_000).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1000).toFixed(1)}ms`;
  return `${seconds.toFixed(2)}s`;
}

export function EventPanel() {
  const events = useEvents();
  const clearEvents = useRuntimeStore((s) => s.clearEvents);

  return (
    <PanelShell
      title="Events"
      toolbar={
        <>
          <span className="font-mono">{events.length}</span>
          <button
            type="button"
            onClick={clearEvents}
            className="rounded border border-line px-1.5 py-0.5 hover:border-accent hover:text-accent"
          >
            Clear
          </button>
        </>
      }
    >
      {events.length === 0 ? (
        <div className="grid h-full place-items-center">
          <p className="font-mono text-xs text-subtle">No events received.</p>
        </div>
      ) : (
        <ul className="divide-y divide-line font-mono text-xs">
          {events
            .slice()
            .reverse()
            .map((event) => {
              const duration = eventDuration(event);
              return (
                <li key={event.event_id} className="flex items-center gap-3 px-3 py-1.5">
                  <span className="shrink-0 text-subtle">
                    {new Date(event.timestamp * 1000).toLocaleTimeString()}
                  </span>
                  <span className={cn("shrink-0", EVENT_COLOR[event.event_type] ?? "text-muted")}>
                    {event.event_type}
                  </span>
                  <span className="truncate text-text">
                    {event.task_name || event.coroutine_name || event.task_id}
                  </span>
                  {duration != null && (
                    <span className="ml-auto shrink-0 text-subtle">{formatDuration(duration)}</span>
                  )}
                  {event.event_type === "asyncio.task.failed" && (
                    <span className="shrink-0 text-danger">{event.exception_type}</span>
                  )}
                </li>
              );
            })}
        </ul>
      )}
    </PanelShell>
  );
}
