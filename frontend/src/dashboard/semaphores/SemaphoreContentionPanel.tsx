/**
 * Stateless presentation layer for the semaphore contention panel.
 *
 * Mirrors :class:`QueuePressurePanel`. Replay-deterministic: feed the
 * same view bundle twice and the rendered DOM is identical.
 */

import { memo, useEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/cn";
import { SemaphoreContentionCard } from "@/dashboard/semaphores/SemaphoreContentionCard";
import { describeSemaphoreCountsAnnouncement } from "@/dashboard/semaphores/SemaphoreContentionAccessibility";
import { getSemaphoreContentionPanelMetrics } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionMetricsCollector";
import { recordSemaphoreContentionTrace } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionTracing";
import type { SemaphoreContentionView } from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export interface SemaphoreContentionPanelStatusProps {
  status: "idle" | "loading" | "ready" | "error";
  errorMessage: string | null;
}

export interface SemaphoreContentionPanelProps {
  views: ReadonlyArray<SemaphoreContentionView>;
  alarmCount: number;
  selectedSemaphoreId: string | null;
  onSelectSemaphore: (semaphoreId: string | null) => void;
  status: SemaphoreContentionPanelStatusProps;
  visibleCap?: number;
  className?: string;
}

const DEFAULT_VISIBLE_CAP = 256;

function SemaphoreContentionPanelImpl({
  views,
  alarmCount,
  selectedSemaphoreId,
  onSelectSemaphore,
  status,
  visibleCap = DEFAULT_VISIBLE_CAP,
  className,
}: SemaphoreContentionPanelProps): JSX.Element {
  const visibleViews = useMemo(
    () => (views.length > visibleCap ? views.slice(0, visibleCap) : views),
    [views, visibleCap],
  );
  const overflow = views.length - visibleViews.length;
  const announcement = useMemo(
    () => describeSemaphoreCountsAnnouncement(views),
    [views],
  );
  const renderedRef = useRef(0);

  useEffect(() => {
    const panelMetrics = getSemaphoreContentionPanelMetrics();
    panelMetrics.recordCardsRendered(visibleViews.length);
    renderedRef.current += 1;
    recordSemaphoreContentionTrace({
      kind: "panel-rendered",
      detail: `views=${visibleViews.length} alarm=${alarmCount}`,
    });
  }, [visibleViews, alarmCount]);

  return (
    <section
      data-testid="semaphore-contention-panel"
      className={cn("semaphore-contention-panel", className)}
      aria-labelledby="semaphore-contention-panel-heading"
    >
      <header className="semaphore-contention-panel__header">
        <h2
          id="semaphore-contention-panel-heading"
          className="semaphore-contention-panel__title"
        >
          Semaphore contention
        </h2>
        <span
          className="semaphore-contention-panel__badge"
          data-testid="semaphore-contention-alarm-count"
          data-tone={alarmCount > 0 ? "alert" : "calm"}
        >
          {alarmCount} alarm{alarmCount === 1 ? "" : "s"}
        </span>
        <span className="semaphore-contention-panel__count">
          {views.length} semaphore{views.length === 1 ? "" : "s"}
        </span>
        {status.status === "loading" && (
          <span
            className="semaphore-contention-panel__status"
            data-status="loading"
          >
            loading…
          </span>
        )}
        {status.status === "error" && (
          <span
            className="semaphore-contention-panel__status"
            data-status="error"
            role="alert"
          >
            {status.errorMessage ?? "failed to load semaphore metrics"}
          </span>
        )}
      </header>

      <div
        className="semaphore-contention-panel__sr-only"
        aria-live="polite"
        data-testid="semaphore-contention-live-region"
      >
        {announcement}
      </div>

      {views.length === 0 ? (
        <p
          className="semaphore-contention-panel__empty"
          data-testid="semaphore-contention-empty"
        >
          No semaphores tracked yet. Semaphore activity will appear here as
          soon as the runtime instruments any{" "}
          <code>asyncio.Semaphore</code>.
        </p>
      ) : (
        <ul className="semaphore-contention-panel__list" role="list">
          {visibleViews.map((view) => (
            <li
              className="semaphore-contention-panel__item"
              key={view.semaphoreId}
            >
              <SemaphoreContentionCard
                view={view}
                selected={view.semaphoreId === selectedSemaphoreId}
                onSelect={onSelectSemaphore}
              />
            </li>
          ))}
          {overflow > 0 && (
            <li
              className="semaphore-contention-panel__item semaphore-contention-panel__overflow"
              data-testid="semaphore-contention-panel-overflow"
            >
              +{overflow} more semaphore{overflow === 1 ? "" : "s"} (raise
              visible cap to inspect)
            </li>
          )}
        </ul>
      )}
    </section>
  );
}

export const SemaphoreContentionPanel = memo(SemaphoreContentionPanelImpl);
