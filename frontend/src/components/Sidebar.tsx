import type { ReactNode } from "react";
import { useMemo } from "react";
import { useRuntimeStore, useTasksById } from "@/state/runtime";
import { cn } from "@/lib/cn";
import type { TaskLifecycleState, TaskSnapshot } from "@/types/runtime";

const STATE_DOT: Record<TaskLifecycleState, string> = {
  created: "bg-subtle",
  running: "bg-success",
  waiting: "bg-accent",
  completed: "bg-muted",
  cancelled: "bg-warning",
  failed: "bg-danger",
};

const STATE_LABEL: Record<TaskLifecycleState, string> = {
  created: "text-subtle",
  running: "text-success",
  waiting: "text-accent",
  completed: "text-subtle",
  cancelled: "text-warning",
  failed: "text-danger",
};

const TERMINAL_STATES: ReadonlySet<TaskLifecycleState> = new Set([
  "completed",
  "cancelled",
  "failed",
]);

function formatDuration(seconds: number): string {
  if (seconds < 0.001) return `${(seconds * 1_000_000).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1000).toFixed(1)}ms`;
  return `${seconds.toFixed(2)}s`;
}

/**
 * Order tasks so that each task immediately follows its parent. Within a
 * sibling group we order by ``created_at`` (tie-break: ``task_id``) for
 * stable rendering. This is a DFS over the parent→children adjacency we
 * derive from the snapshot — depth comes pre-stamped on each row.
 *
 * Orphans (parent_task_id refers to a task we don't have) are surfaced as
 * if they were roots so they stay visible.
 */
function buildHierarchy(tasks: TaskSnapshot[]): TaskSnapshot[] {
  if (tasks.length === 0) return tasks;
  const byId = new Map(tasks.map((t) => [t.task_id, t]));
  const children = new Map<string | null, TaskSnapshot[]>();
  for (const task of tasks) {
    const parentExists = task.parent_task_id != null && byId.has(task.parent_task_id);
    const key = parentExists ? task.parent_task_id : null;
    const bucket = children.get(key) ?? [];
    bucket.push(task);
    children.set(key, bucket);
  }
  const sortSiblings = (rows: TaskSnapshot[]) =>
    rows.sort((a, b) => a.created_at - b.created_at || a.task_id.localeCompare(b.task_id));
  for (const bucket of children.values()) sortSiblings(bucket);

  const out: TaskSnapshot[] = [];
  const visit = (task: TaskSnapshot): void => {
    out.push(task);
    const kids = children.get(task.task_id);
    if (kids) kids.forEach(visit);
  };
  (children.get(null) ?? []).forEach(visit);
  return out;
}

export function Sidebar() {
  const tasksById = useTasksById();
  const selectedTaskId = useRuntimeStore((s) => s.selectedTaskId);
  const selectTask = useRuntimeStore((s) => s.selectTask);

  const hierarchical = useMemo<TaskSnapshot[]>(
    () => buildHierarchy(Object.values(tasksById)),
    [tasksById],
  );

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-line bg-panel">
      <SidebarSection title="Tasks" count={hierarchical.length}>
        {hierarchical.length === 0 ? (
          <EmptyHint label="Waiting for tasks…" />
        ) : (
          <ul className="space-y-1">
            {hierarchical.map((task) => (
              <TaskRow
                key={task.task_id}
                task={task}
                selected={task.task_id === selectedTaskId}
                onSelect={() => selectTask(task.task_id)}
              />
            ))}
          </ul>
        )}
      </SidebarSection>
    </aside>
  );
}

function TaskRow({
  task,
  selected,
  onSelect,
}: {
  task: TaskSnapshot;
  selected: boolean;
  onSelect: () => void;
}) {
  const label = task.task_name || task.coroutine_name || task.task_id.slice(0, 12);
  const isTerminal = TERMINAL_STATES.has(task.state);
  const duration = task.duration_seconds != null ? formatDuration(task.duration_seconds) : null;
  // 8px per depth level — enough to be readable at any depth without pushing
  // the label off the right edge.
  const indentPx = Math.min(task.depth ?? 0, 12) * 8;
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        style={{ paddingLeft: `${8 + indentPx}px` }}
        className={cn(
          "flex w-full items-center gap-2 rounded py-1 pr-2 text-left text-xs",
          "hover:bg-elevated",
          selected && "bg-elevated text-text",
          !selected && (isTerminal ? "text-subtle" : "text-muted"),
        )}
      >
        <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATE_DOT[task.state])} />
        <span className="truncate font-mono">{label}</span>
        {task.child_count > 0 && (
          <span className="shrink-0 font-mono text-[10px] text-subtle">[{task.child_count}]</span>
        )}
        {duration && (
          <span className="ml-auto shrink-0 font-mono text-[10px] text-subtle">{duration}</span>
        )}
        <span
          className={cn(
            "shrink-0 text-[10px] uppercase tracking-widest",
            STATE_LABEL[task.state],
            duration ? "" : "ml-auto",
          )}
        >
          {task.state}
        </span>
      </button>
    </li>
  );
}

function SidebarSection({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: ReactNode;
}) {
  return (
    <section className="flex min-h-0 flex-col border-b border-line last:border-b-0">
      <header className="flex h-9 items-center justify-between px-3">
        <span className="text-xs font-medium uppercase tracking-widest text-muted">{title}</span>
        {count !== undefined && <span className="font-mono text-xs text-subtle">{count}</span>}
      </header>
      <div className="flex-1 overflow-y-auto px-3 pb-3">{children}</div>
    </section>
  );
}

function EmptyHint({ label }: { label: string }) {
  return <p className="text-xs text-subtle">{label}</p>;
}
