/**
 * Queue pressure dashboard.
 *
 * A dense, developer-oriented surface over the same data the legacy
 * panel rendered — projected through :func:`useQueuePressureViewsBundle`,
 * hydrated by :func:`useQueuePressureHydration`, and kept live by
 * :func:`useQueuePressureWebsocketBridge`. Backend / projection /
 * hydration are unchanged. This is presentation only.
 */

import { useMemo } from "react";
import { cn } from "@/lib/cn";
import { Card } from "@/ui/primitives/Card";
import { Badge } from "@/ui/primitives/Badge";
import { EmptyState } from "@/ui/feedback/EmptyState";
import type { Intent } from "@/ui/theme/tokens";
import { useQueuePressureHydration } from "@/dashboard/queues/hooks/useQueuePressureHydration";
import { useQueuePressureWebsocketBridge } from "@/dashboard/queues/hooks/useQueuePressureWebsocketBridge";
import { useQueuePressureSelection } from "@/dashboard/queues/hooks/useQueuePressureSelection";
import { useQueuePressureViewsBundle } from "@/dashboard/queues/hooks/useQueuePressureViews";
import {
  useQueuePressureErrorMessage,
  useQueuePressureMarkers,
  useQueuePressureStatus,
} from "@/dashboard/queues/selectors/QueuePressureSelectors";
import { QueuePressureTimeline } from "@/dashboard/queues/QueuePressureTimeline";
import { severityLabel } from "@/dashboard/queues/QueuePressureSeverity";
import type {
  QueuePressureSeverity,
  QueuePressureView,
} from "@/dashboard/queues/models/QueuePressureModels";

export function QueuesPage(): JSX.Element {
  useQueuePressureHydration({ enabled: true });
  useQueuePressureWebsocketBridge({ enabled: true });

  const { bySeverityDescending } = useQueuePressureViewsBundle();
  const { selectedQueueId, selectQueue } = useQueuePressureSelection();
  const status = useQueuePressureStatus();
  const errorMessage = useQueuePressureErrorMessage();
  const markers = useQueuePressureMarkers();
  const summary = useMemo(() => buildSummary(bySeverityDescending), [bySeverityDescending]);

  const hasQueues = bySeverityDescending.length > 0;
  const isLoading = status === "loading" && !hasQueues;
  const isError = status === "error";

  return (
    <div
      data-queues-page="true"
      className="flex h-full min-h-0 w-full min-w-0 flex-col gap-4 overflow-y-auto px-4 py-4"
    >
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-mono text-sm uppercase tracking-widest text-text">Queues</h1>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {summary.total} tracked
          </span>
        </div>
        {isError && (
          <Badge intent="danger" role="alert">
            {errorMessage ?? "Failed to load queue metrics"}
          </Badge>
        )}
        {isLoading && (
          <Badge intent="accent" aria-live="polite">
            Loading
          </Badge>
        )}
      </header>

      <Section title="Queue summary">
        {hasQueues ? (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
            <SummaryCell label="Total queues" value={String(summary.total)} />
            <SummaryCell
              label="Saturated"
              value={String(summary.saturated)}
              intent={summary.saturated > 0 ? "warning" : "default"}
            />
            <SummaryCell
              label="Alarm"
              value={String(summary.alarm)}
              intent={summary.alarm > 0 ? "danger" : "default"}
            />
            <SummaryCell
              label="Calm"
              value={String(summary.calm)}
              intent={summary.calm > 0 ? "success" : "default"}
            />
            <SummaryCell
              label="Avg occupancy"
              value={formatPercent(summary.avgOccupancy)}
            />
            <SummaryCell
              label="Highest pressure"
              value={summary.maxPressure.toFixed(2)}
              sub={summary.maxPressureName !== null ? summary.maxPressureName : undefined}
              intent={summary.maxPressure >= 0.7 ? "danger" : summary.maxPressure >= 0.4 ? "warning" : "default"}
            />
          </div>
        ) : (
          <SectionEmpty />
        )}
      </Section>

      {hasQueues && markers.length > 0 && (
        <Card padding="sm">
          <div className="flex items-baseline justify-between pb-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Pressure timeline
            </span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
              {markers.length} marker{markers.length === 1 ? "" : "s"}
            </span>
          </div>
          <QueuePressureTimeline markers={markers} heightPx={28} />
        </Card>
      )}

      <Section title="Queues">
        {hasQueues ? (
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(22rem, 1fr))" }}
          >
            {bySeverityDescending.map((view) => (
              <QueueCard
                key={view.queueId}
                view={view}
                selected={view.queueId === selectedQueueId}
                onSelect={selectQueue}
              />
            ))}
          </div>
        ) : isLoading ? (
          <SectionEmpty />
        ) : (
          <EmptyState
            title="No queues tracked yet"
            description="Queue activity appears here as soon as your runtime instruments an asyncio.Queue."
          />
        )}
      </Section>
    </div>
  );
}

// ── Summary projection ────────────────────────────────────────────────────

interface QueueSummary {
  total: number;
  saturated: number;
  alarm: number;
  calm: number;
  avgOccupancy: number;
  maxPressure: number;
  maxPressureName: string | null;
}

function buildSummary(views: readonly QueuePressureView[]): QueueSummary {
  if (views.length === 0) {
    return {
      total: 0,
      saturated: 0,
      alarm: 0,
      calm: 0,
      avgOccupancy: 0,
      maxPressure: 0,
      maxPressureName: null,
    };
  }
  let saturated = 0;
  let alarm = 0;
  let calm = 0;
  let occupancySum = 0;
  let maxPressure = -Infinity;
  let maxPressureName: string | null = null;
  for (const view of views) {
    if (view.severity === "saturated") saturated += 1;
    else if (view.severity === "warning" || view.severity === "critical") alarm += 1;
    else calm += 1;
    occupancySum += Number.isFinite(view.occupancyRatio) ? view.occupancyRatio : 0;
    if (view.pressureScore > maxPressure) {
      maxPressure = view.pressureScore;
      maxPressureName = view.displayName;
    }
  }
  return {
    total: views.length,
    saturated,
    alarm,
    calm,
    avgOccupancy: occupancySum / views.length,
    maxPressure: Number.isFinite(maxPressure) ? maxPressure : 0,
    maxPressureName,
  };
}

// ── Queue card ────────────────────────────────────────────────────────────

interface QueueCardProps {
  view: QueuePressureView;
  selected: boolean;
  onSelect: (queueId: string | null) => void;
}

function QueueCard({ view, selected, onSelect }: QueueCardProps): JSX.Element {
  const intent = severityIntent(view.severity);
  const label = severityLabel(view.severity).toUpperCase();
  const occupancyPct = clampRatio(view.occupancyRatio);
  return (
    <Card
      padding="sm"
      intent={intent}
      className={cn(
        "flex flex-col gap-3 transition-colors",
        selected ? "ring-1 ring-accent" : "",
      )}
      data-queue-id={view.queueId}
      data-severity={view.severity}
      data-selected={selected ? "true" : undefined}
    >
      <header className="flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => onSelect(selected ? null : view.queueId)}
          className="flex min-w-0 flex-col items-start gap-0.5 text-left"
          aria-pressed={selected}
        >
          <span className="truncate font-mono text-sm text-text">{view.displayName}</span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {view.queueKind}
          </span>
        </button>
        <Badge intent={intent} aria-label={`Status ${label}`}>
          {label}
        </Badge>
      </header>

      <OccupancyBar
        ratio={occupancyPct}
        intent={intent}
        currentSize={view.currentSize}
        maxsize={view.maxsize}
      />

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 font-mono text-xs">
        <Metric label="Size" value={formatSize(view.currentSize, view.maxsize)} />
        <Metric label="Occupancy" value={formatPercent(view.occupancyRatio)} />
        <Metric label="Pressure" value={view.pressureScore.toFixed(2)} />
        <Metric
          label="Δ Producer−Consumer"
          value={formatDelta(view.producerConsumerDelta)}
          intent={
            view.producerConsumerDelta > 0
              ? "warning"
              : view.producerConsumerDelta < 0
                ? "success"
                : undefined
          }
        />
        <Metric label="Put/sec" value={formatRate(view.putRate)} />
        <Metric label="Get/sec" value={formatRate(view.getRate)} />
      </dl>

      {(view.blockedProducers > 0 || view.blockedConsumers > 0) && (
        <footer className="flex flex-wrap items-center gap-2 border-t border-line/60 pt-2">
          {view.blockedProducers > 0 && (
            <Badge intent="warning">
              {view.blockedProducers} blocked producer
              {view.blockedProducers === 1 ? "" : "s"}
            </Badge>
          )}
          {view.blockedConsumers > 0 && (
            <Badge intent="warning">
              {view.blockedConsumers} blocked consumer
              {view.blockedConsumers === 1 ? "" : "s"}
            </Badge>
          )}
        </footer>
      )}
    </Card>
  );
}

function OccupancyBar({
  ratio,
  intent,
  currentSize,
  maxsize,
}: {
  ratio: number;
  intent: Intent;
  currentSize: number;
  maxsize: number;
}) {
  const widthPct = Math.max(2, Math.min(100, ratio * 100));
  const colorClass =
    intent === "danger"
      ? "bg-danger"
      : intent === "warning"
        ? "bg-warning"
        : intent === "success"
          ? "bg-success"
          : "bg-accent";
  return (
    <div
      role="meter"
      aria-valuemin={0}
      aria-valuemax={maxsize > 0 ? maxsize : 100}
      aria-valuenow={currentSize}
      aria-label={`Occupancy ${formatPercent(ratio)}`}
      className="relative h-1.5 w-full overflow-hidden rounded bg-elevated"
    >
      <div
        className={cn("h-full", colorClass)}
        style={{ width: `${widthPct.toFixed(1)}%` }}
        aria-hidden="true"
      />
    </div>
  );
}

function Metric({
  label,
  value,
  intent,
}: {
  label: string;
  value: string;
  intent?: Intent;
}) {
  const valueColor =
    intent === "danger"
      ? "text-danger"
      : intent === "warning"
        ? "text-warning"
        : intent === "success"
          ? "text-success"
          : "text-text";
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="truncate text-[10px] uppercase tracking-widest text-muted">{label}</dt>
      <dd className={cn("tabular-nums", valueColor)}>{value}</dd>
    </div>
  );
}

// ── Section building blocks ──────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-mono text-[10px] uppercase tracking-widest text-muted">{title}</h2>
      {children}
    </section>
  );
}

function SectionEmpty() {
  return (
    <Card padding="md">
      <p className="font-mono text-xs text-subtle">No data available</p>
    </Card>
  );
}

function SummaryCell({
  label,
  value,
  sub,
  intent = "default",
}: {
  label: string;
  value: string;
  sub?: string;
  intent?: Intent;
}) {
  return (
    <Card padding="sm" intent={intent} className="flex flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className="truncate font-mono text-base tabular-nums text-text">{value}</span>
      {sub !== undefined && (
        <span className="truncate font-mono text-[10px] uppercase tracking-widest text-subtle">
          {sub}
        </span>
      )}
    </Card>
  );
}

// ── Formatting + severity mapping ────────────────────────────────────────

function severityIntent(severity: QueuePressureSeverity): Intent {
  switch (severity) {
    case "calm":
      return "success";
    case "warning":
      return "warning";
    case "saturated":
      return "warning";
    case "critical":
      return "danger";
    default:
      return "default";
  }
}

function clampRatio(value: number): number {
  if (!Number.isFinite(value) || value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return `${Math.round(clampRatio(value) * 100)}%`;
}

function formatSize(current: number, max: number): string {
  if (max > 0) return `${current} / ${max}`;
  return `${current}`;
}

function formatRate(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0/s";
  if (value >= 100) return `${value.toFixed(0)}/s`;
  if (value >= 10) return `${value.toFixed(1)}/s`;
  return `${value.toFixed(2)}/s`;
}

function formatDelta(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  const formatted = Math.abs(value) >= 10 ? value.toFixed(0) : value.toFixed(2);
  return value > 0 ? `+${formatted}` : formatted;
}
