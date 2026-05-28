/**
 * Stateless presentation layer for the queue pressure panel.
 *
 * Mirrors :class:`BlockingWarningsPanel` — the container wires the
 * store + hooks, the panel renders props. Replay-deterministic: feed
 * the same views twice and the DOM is identical.
 */

import { memo, useEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/cn";
import { QueuePressureCard } from "@/dashboard/queues/QueuePressureCard";
import { describeQueueCountsAnnouncement } from "@/dashboard/queues/QueuePressureAccessibility";
import { getQueuePressurePanelMetrics } from "@/dashboard/queues/diagnostics/QueuePressureMetricsCollector";
import { recordQueuePressureTrace } from "@/dashboard/queues/diagnostics/QueuePressureTracing";
import type {
  QueuePressureView,
} from "@/dashboard/queues/models/QueuePressureModels";

export interface QueuePressurePanelStatusProps {
  status: "idle" | "loading" | "ready" | "error";
  errorMessage: string | null;
}

export interface QueuePressurePanelProps {
  /** Severity-ordered views the panel renders. */
  views: ReadonlyArray<QueuePressureView>;
  /** Number of queues with severity >= warning — drives the badge. */
  alarmCount: number;
  selectedQueueId: string | null;
  onSelectQueue: (queueId: string | null) => void;
  status: QueuePressurePanelStatusProps;
  /** Visible-cap override for tests + dense streams. Defaults to 256. */
  visibleCap?: number;
  className?: string;
}

const DEFAULT_VISIBLE_CAP = 256;

function QueuePressurePanelImpl({
  views,
  alarmCount,
  selectedQueueId,
  onSelectQueue,
  status,
  visibleCap = DEFAULT_VISIBLE_CAP,
  className,
}: QueuePressurePanelProps): JSX.Element {
  const visibleViews = useMemo(
    () => (views.length > visibleCap ? views.slice(0, visibleCap) : views),
    [views, visibleCap],
  );
  const overflow = views.length - visibleViews.length;
  const announcement = useMemo(() => describeQueueCountsAnnouncement(views), [views]);
  const renderedRef = useRef(0);

  useEffect(() => {
    const panelMetrics = getQueuePressurePanelMetrics();
    panelMetrics.recordCardsRendered(visibleViews.length);
    renderedRef.current += 1;
    recordQueuePressureTrace({
      kind: "panel-rendered",
      detail: `views=${visibleViews.length} alarm=${alarmCount}`,
    });
  }, [visibleViews, alarmCount]);

  return (
    <section
      data-testid="queue-pressure-panel"
      className={cn("queue-pressure-panel", className)}
      aria-labelledby="queue-pressure-panel-heading"
    >
      <header className="queue-pressure-panel__header">
        <h2 id="queue-pressure-panel-heading" className="queue-pressure-panel__title">
          Queue pressure
        </h2>
        <span
          className="queue-pressure-panel__badge"
          data-testid="queue-pressure-alarm-count"
          data-tone={alarmCount > 0 ? "alert" : "calm"}
        >
          {alarmCount} alarm{alarmCount === 1 ? "" : "s"}
        </span>
        <span className="queue-pressure-panel__count">
          {views.length} queue{views.length === 1 ? "" : "s"}
        </span>
        {status.status === "loading" && (
          <span className="queue-pressure-panel__status" data-status="loading">
            loading…
          </span>
        )}
        {status.status === "error" && (
          <span
            className="queue-pressure-panel__status"
            data-status="error"
            role="alert"
          >
            {status.errorMessage ?? "failed to load queue metrics"}
          </span>
        )}
      </header>

      <div className="queue-pressure-panel__sr-only" aria-live="polite" data-testid="queue-pressure-live-region">
        {announcement}
      </div>

      {views.length === 0 ? (
        <p className="queue-pressure-panel__empty" data-testid="queue-pressure-empty">
          No queues tracked yet. Queue activity will appear here as soon as the
          runtime instruments any <code>asyncio.Queue</code>.
        </p>
      ) : (
        <ul className="queue-pressure-panel__list" role="list">
          {visibleViews.map((view) => (
            <li className="queue-pressure-panel__item" key={view.queueId}>
              <QueuePressureCard
                view={view}
                selected={view.queueId === selectedQueueId}
                onSelect={onSelectQueue}
              />
            </li>
          ))}
          {overflow > 0 && (
            <li
              className="queue-pressure-panel__item queue-pressure-panel__overflow"
              data-testid="queue-pressure-panel-overflow"
            >
              +{overflow} more queue{overflow === 1 ? "" : "s"} (raise visible cap to inspect)
            </li>
          )}
        </ul>
      )}
    </section>
  );
}

export const QueuePressurePanel = memo(QueuePressurePanelImpl);
