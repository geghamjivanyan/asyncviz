/**
 * Expanded inspector body — shown when a group is selected.
 *
 * Composes the lifecycle summary + escalation timeline + capture
 * chips into a single vertically stacked panel. Stateless; consumers
 * decide whether to render it inline (current layout) or in a drawer.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import type { BlockingWarningView } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { BlockingWarningLifecycleSummary } from "@/dashboard/warnings/blocking/BlockingWarningLifecycle";
import { BlockingWarningTimeline } from "@/dashboard/warnings/blocking/BlockingWarningTimeline";
import { BlockingWarningCaptures } from "@/dashboard/warnings/blocking/BlockingWarningCaptures";

export interface BlockingWarningInspectorProps {
  view: BlockingWarningView;
  onSelectCapture?: (captureId: number, groupId: string) => void;
  onSelectTask?: (taskId: string) => void;
  className?: string;
}

function BlockingWarningInspectorImpl({
  view,
  onSelectCapture,
  onSelectTask,
  className,
}: BlockingWarningInspectorProps) {
  return (
    <section
      className={cn("flex flex-col gap-3", className)}
      aria-label={`Inspecting warning ${view.warningId}`}
      data-testid="blocking-warning-inspector"
    >
      <BlockingWarningLifecycleSummary view={view} />
      {view.taskName !== null || view.coroutineName !== null ? (
        <dl
          className="flex flex-wrap gap-4 text-xs font-mono"
          aria-label="Correlated task"
        >
          {view.taskName !== null && (
            <div className="flex flex-col">
              <dt className="text-subtle uppercase tracking-wider text-[10px]">Task</dt>
              <dd>
                <button
                  type="button"
                  onClick={() =>
                    view.taskId !== null && onSelectTask?.(view.taskId)
                  }
                  className="text-accent hover:underline"
                  aria-label={`Focus task ${view.taskName}`}
                  data-testid="blocking-warning-task-link"
                  disabled={view.taskId === null}
                >
                  {view.taskName}
                </button>
              </dd>
            </div>
          )}
          {view.coroutineName !== null && (
            <div className="flex flex-col">
              <dt className="text-subtle uppercase tracking-wider text-[10px]">Coroutine</dt>
              <dd className="text-text">{view.coroutineName}</dd>
            </div>
          )}
        </dl>
      ) : null}
      <BlockingWarningTimeline view={view} />
      <BlockingWarningCaptures view={view} onSelectCapture={onSelectCapture} />
    </section>
  );
}

export const BlockingWarningInspector = memo(BlockingWarningInspectorImpl);
