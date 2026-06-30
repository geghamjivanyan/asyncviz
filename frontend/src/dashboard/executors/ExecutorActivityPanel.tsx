/**
 * Stateless presentation layer for the executor activity panel.
 */

import { memo, useEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/cn";
import { ExecutorActivityCard } from "@/dashboard/executors/ExecutorActivityCard";
import { describeExecutorCountsAnnouncement } from "@/dashboard/executors/ExecutorActivityAccessibility";
import { getExecutorActivityPanelMetrics } from "@/dashboard/executors/diagnostics/ExecutorActivityMetricsCollector";
import { recordExecutorActivityTrace } from "@/dashboard/executors/diagnostics/ExecutorActivityTracing";
import type { ExecutorActivityView } from "@/dashboard/executors/models/ExecutorActivityModels";

export interface ExecutorActivityPanelStatusProps {
  status: "idle" | "loading" | "ready" | "error";
  errorMessage: string | null;
}

export interface ExecutorActivityPanelProps {
  views: ReadonlyArray<ExecutorActivityView>;
  alarmCount: number;
  selectedExecutorId: string | null;
  onSelectExecutor: (executorId: string | null) => void;
  status: ExecutorActivityPanelStatusProps;
  visibleCap?: number;
  className?: string;
}

const DEFAULT_VISIBLE_CAP = 256;

function ExecutorActivityPanelImpl({
  views,
  alarmCount,
  selectedExecutorId,
  onSelectExecutor,
  status,
  visibleCap = DEFAULT_VISIBLE_CAP,
  className,
}: ExecutorActivityPanelProps): JSX.Element {
  const visibleViews = useMemo(
    () => (views.length > visibleCap ? views.slice(0, visibleCap) : views),
    [views, visibleCap],
  );
  const overflow = views.length - visibleViews.length;
  const announcement = useMemo(() => describeExecutorCountsAnnouncement(views), [views]);
  const renderedRef = useRef(0);

  useEffect(() => {
    const panelMetrics = getExecutorActivityPanelMetrics();
    panelMetrics.recordCardsRendered(visibleViews.length);
    renderedRef.current += 1;
    recordExecutorActivityTrace({
      kind: "panel-rendered",
      detail: `views=${visibleViews.length} alarm=${alarmCount}`,
    });
  }, [visibleViews, alarmCount]);

  return (
    <section
      data-testid="executor-activity-panel"
      className={cn("executor-activity-panel", className)}
      aria-labelledby="executor-activity-panel-heading"
    >
      <header className="executor-activity-panel__header">
        <h2 id="executor-activity-panel-heading" className="executor-activity-panel__title">
          Executor activity
        </h2>
        <span
          className="executor-activity-panel__badge"
          data-testid="executor-activity-alarm-count"
          data-tone={alarmCount > 0 ? "alert" : "calm"}
        >
          {alarmCount} alarm{alarmCount === 1 ? "" : "s"}
        </span>
        <span className="executor-activity-panel__count">
          {views.length} executor{views.length === 1 ? "" : "s"}
        </span>
        {status.status === "loading" && (
          <span className="executor-activity-panel__status" data-status="loading">
            loading…
          </span>
        )}
        {status.status === "error" && (
          <span className="executor-activity-panel__status" data-status="error" role="alert">
            {status.errorMessage ?? "failed to load executor metrics"}
          </span>
        )}
      </header>

      <div
        className="executor-activity-panel__sr-only"
        aria-live="polite"
        data-testid="executor-activity-live-region"
      >
        {announcement}
      </div>

      {views.length === 0 ? (
        <p className="executor-activity-panel__empty" data-testid="executor-activity-empty">
          No executors tracked yet. Executor activity will appear here as soon as the runtime
          instruments any <code>loop.run_in_executor</code> call.
        </p>
      ) : (
        <ul className="executor-activity-panel__list" role="list">
          {visibleViews.map((view) => (
            <li className="executor-activity-panel__item" key={view.executorId}>
              <ExecutorActivityCard
                view={view}
                selected={view.executorId === selectedExecutorId}
                onSelect={onSelectExecutor}
              />
            </li>
          ))}
          {overflow > 0 && (
            <li
              className="executor-activity-panel__item executor-activity-panel__overflow"
              data-testid="executor-activity-panel-overflow"
            >
              +{overflow} more executor{overflow === 1 ? "" : "s"} (raise visible cap to inspect)
            </li>
          )}
        </ul>
      )}
    </section>
  );
}

export const ExecutorActivityPanel = memo(ExecutorActivityPanelImpl);
