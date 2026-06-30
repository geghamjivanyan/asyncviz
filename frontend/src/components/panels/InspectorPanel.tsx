import { useSelectedTask, useSelectedTaskId } from "@/state/runtime";
import type { TaskSnapshot } from "@/types/runtime";
import { PanelShell } from "./PanelShell";

const CANCELLATION_ORIGIN_LABEL: Record<string, string> = {
  explicit: "Cancelled by user",
  shutdown: "Cancelled during shutdown",
  timeout: "Cancelled by timeout",
  parent: "Cancelled by parent task",
};

function formatCancellationOrigin(origin: string): string {
  return CANCELLATION_ORIGIN_LABEL[origin] ?? `Cancelled (${origin})`;
}

export function InspectorPanel() {
  const selectedTaskId = useSelectedTaskId();
  const task = useSelectedTask();

  return (
    <PanelShell title="Inspector">
      {task ? (
        <TaskDetails task={task} />
      ) : (
        <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
          {selectedTaskId ? (
            <>
              <p className="text-[10px] uppercase tracking-widest text-muted">
                Task no longer tracked
              </p>
              <p className="font-mono text-xs text-subtle">
                Task {selectedTaskId.slice(0, 8)}… is no longer in the runtime snapshot. Pick
                another task from the sidebar or the live table.
              </p>
            </>
          ) : (
            <>
              <p className="text-[10px] uppercase tracking-widest text-muted">No task selected</p>
              <p className="font-mono text-xs leading-relaxed text-subtle">
                Pick a task from the sidebar, the live table, or the timeline to see its lifecycle,
                timing, parent/child relationships, and any warnings it raised.
              </p>
            </>
          )}
        </div>
      )}
    </PanelShell>
  );
}

function TaskDetails({ task }: { task: TaskSnapshot }) {
  return (
    <div className="space-y-3 p-3 font-mono text-xs text-text">
      <Field label="Task ID" value={task.task_id} mono />
      <Field label="State" value={task.state} />
      {task.coroutine_name && <Field label="Coroutine" value={task.coroutine_name} />}
      {task.task_name && <Field label="Name" value={task.task_name} />}
      {task.parent_task_id && <Field label="Parent" value={task.parent_task_id} mono />}
      {task.root_task_id && task.root_task_id !== task.task_id && (
        <Field label="Root" value={task.root_task_id} mono />
      )}
      <Field label="Depth" value={String(task.depth)} />
      {task.child_count > 0 && <Field label="Children" value={String(task.child_count)} />}
      {task.ancestor_chain.length > 0 && (
        <Field label="Ancestors" value={task.ancestor_chain.join(" → ")} mono />
      )}
      <Field label="Created" value={new Date(task.created_at * 1000).toISOString()} />
      <Field label="Updated" value={new Date(task.updated_at * 1000).toISOString()} />
      {task.duration_seconds != null && (
        <Field label="Duration" value={`${task.duration_seconds.toFixed(4)} s`} />
      )}
      {task.exception_type && (
        <Field
          label="Exception"
          value={`${task.exception_type}: ${task.exception_message ?? ""}`}
        />
      )}
      {task.cancellation_origin && (
        <Field label="Cancellation" value={formatCancellationOrigin(task.cancellation_origin)} />
      )}
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-muted">{label}</div>
      <div className={mono ? "break-all text-text" : "text-text"}>{value}</div>
    </div>
  );
}
