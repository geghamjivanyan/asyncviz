/**
 * Semaphore contention dashboard.
 *
 * Consumes the same view bundle the legacy panel did
 * (:func:`useSemaphoreContentionViewsBundle`) plus the existing
 * hydration and websocket bridge hooks. Backend / projection / store
 * are unchanged — this is a presentation-only rewrite.
 */

import { useMemo } from "react";
import { cn } from "@/lib/cn";
import { Card } from "@/ui/primitives/Card";
import { Badge } from "@/ui/primitives/Badge";
import { EmptyState } from "@/ui/feedback/EmptyState";
import type { Intent } from "@/ui/theme/tokens";
import { useSemaphoreContentionHydration } from "@/dashboard/semaphores/hooks/useSemaphoreContentionHydration";
import { useSemaphoreContentionWebsocketBridge } from "@/dashboard/semaphores/hooks/useSemaphoreContentionWebsocketBridge";
import { useSemaphoreContentionSelection } from "@/dashboard/semaphores/hooks/useSemaphoreContentionSelection";
import { useSemaphoreContentionViewsBundle } from "@/dashboard/semaphores/hooks/useSemaphoreContentionViews";
import {
  useSemaphoreContentionErrorMessage,
  useSemaphoreContentionMarkers,
  useSemaphoreContentionStatus,
} from "@/dashboard/semaphores/selectors/SemaphoreContentionSelectors";
import { SemaphoreContentionTimeline } from "@/dashboard/semaphores/SemaphoreContentionTimeline";
import type { SemaphoreContentionView } from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export function SemaphoresPage(): JSX.Element {
  useSemaphoreContentionHydration({ enabled: true });
  useSemaphoreContentionWebsocketBridge({ enabled: true });

  const { bySeverityDescending } = useSemaphoreContentionViewsBundle();
  const { selectedSemaphoreId, selectSemaphore } = useSemaphoreContentionSelection();
  const status = useSemaphoreContentionStatus();
  const errorMessage = useSemaphoreContentionErrorMessage();
  const markers = useSemaphoreContentionMarkers();
  const summary = useMemo(() => buildSummary(bySeverityDescending), [bySeverityDescending]);

  const hasSemaphores = bySeverityDescending.length > 0;
  const isLoading = status === "loading" && !hasSemaphores;
  const isError = status === "error";

  return (
    <div
      data-semaphores-page="true"
      className="flex h-full min-h-0 w-full min-w-0 flex-col gap-4 overflow-y-auto px-4 py-4"
    >
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-mono text-sm uppercase tracking-widest text-text">Semaphores</h1>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {summary.total} tracked
          </span>
        </div>
        {isError && (
          <Badge intent="danger" role="alert">
            {errorMessage ?? "Failed to load semaphore metrics"}
          </Badge>
        )}
        {isLoading && (
          <Badge intent="accent" aria-live="polite">
            Loading
          </Badge>
        )}
      </header>

      <Section title="Semaphore summary">
        {hasSemaphores ? (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
            <SummaryCell label="Total" value={String(summary.total)} />
            <SummaryCell
              label="Saturated"
              value={String(summary.saturated)}
              intent={summary.saturated > 0 ? "warning" : "default"}
            />
            <SummaryCell
              label="Contended"
              value={String(summary.contended)}
              intent={
                summary.critical > 0
                  ? "danger"
                  : summary.contended > 0
                    ? "warning"
                    : "default"
              }
            />
            <SummaryCell
              label="Idle"
              value={String(summary.idle)}
              intent={summary.idle > 0 ? "success" : "default"}
            />
            <SummaryCell label="Avg utilization" value={formatPercent(summary.avgUtilization)} />
            <SummaryCell label="Avg waiters" value={summary.avgWaiters.toFixed(2)} />
            <SummaryCell
              label="Peak wait time"
              value={formatSeconds(summary.peakWaitSeconds)}
              sub={summary.peakWaitName ?? undefined}
              intent={summary.peakWaitSeconds >= 1 ? "warning" : "default"}
            />
          </div>
        ) : (
          <SectionEmpty />
        )}
      </Section>

      {hasSemaphores && markers.length > 0 && (
        <Card padding="sm">
          <div className="flex items-baseline justify-between pb-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Contention timeline
            </span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
              {markers.length} marker{markers.length === 1 ? "" : "s"}
            </span>
          </div>
          <SemaphoreContentionTimeline markers={markers} heightPx={28} />
        </Card>
      )}

      <Section title="Semaphores">
        {hasSemaphores ? (
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(22rem, 1fr))" }}
          >
            {bySeverityDescending.map((view) => (
              <SemaphoreCard
                key={view.semaphoreId}
                view={view}
                selected={view.semaphoreId === selectedSemaphoreId}
                onSelect={selectSemaphore}
              />
            ))}
          </div>
        ) : isLoading ? (
          <SectionEmpty />
        ) : (
          <EmptyState
            title="No semaphores observed."
            description="Semaphore activity appears here as soon as your runtime instruments an asyncio.Semaphore or BoundedSemaphore."
          />
        )}
      </Section>
    </div>
  );
}

// ── Summary projection ────────────────────────────────────────────────────

interface SemaphoreSummary {
  total: number;
  saturated: number;
  contended: number;
  critical: number;
  idle: number;
  avgUtilization: number;
  avgWaiters: number;
  peakWaitSeconds: number;
  peakWaitName: string | null;
}

function buildSummary(views: readonly SemaphoreContentionView[]): SemaphoreSummary {
  if (views.length === 0) {
    return {
      total: 0,
      saturated: 0,
      contended: 0,
      critical: 0,
      idle: 0,
      avgUtilization: 0,
      avgWaiters: 0,
      peakWaitSeconds: 0,
      peakWaitName: null,
    };
  }
  let saturated = 0;
  let contended = 0;
  let critical = 0;
  let idle = 0;
  let utilSum = 0;
  let waitersSum = 0;
  let peakWait = 0;
  let peakWaitName: string | null = null;
  for (const view of views) {
    if (view.severity === "saturated") saturated += 1;
    else if (view.severity === "warning") contended += 1;
    else if (view.severity === "critical") {
      contended += 1;
      critical += 1;
    } else if (view.severity === "calm" && view.utilizationRatio === 0 && view.waiterCount === 0) {
      idle += 1;
    }
    utilSum += Number.isFinite(view.utilizationRatio) ? view.utilizationRatio : 0;
    waitersSum += Number.isFinite(view.waiterCount) ? view.waiterCount : 0;
    if (Number.isFinite(view.maxWaitSeconds) && view.maxWaitSeconds > peakWait) {
      peakWait = view.maxWaitSeconds;
      peakWaitName = view.displayName;
    }
  }
  return {
    total: views.length,
    saturated,
    contended,
    critical,
    idle,
    avgUtilization: utilSum / views.length,
    avgWaiters: waitersSum / views.length,
    peakWaitSeconds: peakWait,
    peakWaitName,
  };
}

// ── Semaphore card ────────────────────────────────────────────────────────

interface SemaphoreCardProps {
  view: SemaphoreContentionView;
  selected: boolean;
  onSelect: (semaphoreId: string | null) => void;
}

function SemaphoreCard({ view, selected, onSelect }: SemaphoreCardProps): JSX.Element {
  const status = deriveStatus(view);
  const intent = STATUS_INTENT[status];
  const fullyUtilized = view.utilizationRatio >= 1 || status === "saturated";
  const peakWaitIntent: Intent | undefined =
    view.maxWaitSeconds >= 1
      ? "danger"
      : view.maxWaitSeconds >= 0.25
        ? "warning"
        : undefined;
  return (
    <Card
      padding="sm"
      intent={intent}
      className={cn(
        "flex flex-col gap-4 transition-colors",
        selected ? "ring-1 ring-accent" : "",
      )}
      data-semaphore-id={view.semaphoreId}
      data-severity={view.severity}
      data-status={status}
      data-selected={selected ? "true" : undefined}
    >
      <header className="flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => onSelect(selected ? null : view.semaphoreId)}
          className="flex min-w-0 flex-col items-start gap-0.5 text-left"
          aria-pressed={selected}
        >
          <span className="truncate font-mono text-sm text-text">{view.displayName}</span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {view.semaphoreKind}
          </span>
        </button>
        <Badge intent={intent} aria-label={`Status ${STATUS_LABEL[status]}`}>
          {STATUS_LABEL[status]}
        </Badge>
      </header>

      {/* Capacity — utilization headline + bar */}
      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3 font-mono">
          <span className="text-[10px] uppercase tracking-widest text-muted">Utilization</span>
          <span className="flex items-baseline gap-3">
            <span
              className={cn(
                "text-sm tabular-nums",
                fullyUtilized ? "text-warning" : "text-text",
              )}
            >
              {formatPercent(view.utilizationRatio)}
            </span>
            <span className="text-[10px] uppercase tracking-widest text-subtle">
              {formatPermits(view.permitsInUse, view.initialValue)} permits
            </span>
          </span>
        </div>
        <UtilizationBar
          ratio={view.utilizationRatio}
          intent={intent}
          used={view.permitsInUse}
          max={view.initialValue}
        />
      </section>

      {/* Waiters */}
      <MetricGroup label="Waiters">
        <Metric
          label="Current"
          value={String(view.waiterCount)}
          intent={view.waiterCount > 0 ? "warning" : undefined}
        />
        <Metric label="Peak" value={String(view.peakWaiterCount)} />
      </MetricGroup>

      {/* Timing */}
      <MetricGroup label="Timing">
        <Metric label="Avg wait" value={formatSeconds(view.meanWaitSeconds)} />
        <Metric
          label="Max wait"
          value={formatSeconds(view.maxWaitSeconds)}
          intent={peakWaitIntent}
        />
      </MetricGroup>

      {/* Operations */}
      <MetricGroup label="Operations">
        <Metric
          label="Blocked acquires"
          value={String(view.blockedAcquireCount)}
          intent={view.blockedAcquireCount > 0 ? "warning" : undefined}
        />
        <Metric label="Bound" value={formatBound(view.boundValue, view.initialValue)} />
        <Metric label="Acquired" value={String(view.acquireCount)} />
        <Metric label="Released" value={String(view.releaseCount)} />
      </MetricGroup>

      {(view.waiterCount > 0 || view.cancelledWaitCount > 0) && (
        <footer className="flex flex-wrap items-center gap-2 border-t border-line/60 pt-2">
          {view.waiterCount > 0 && (
            <Badge intent="warning">
              {view.waiterCount} waiter{view.waiterCount === 1 ? "" : "s"} parked
            </Badge>
          )}
          {view.cancelledWaitCount > 0 && (
            <Badge intent="default">
              {view.cancelledWaitCount} wait{view.cancelledWaitCount === 1 ? "" : "s"} cancelled
            </Badge>
          )}
        </footer>
      )}
    </Card>
  );
}

function MetricGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-1.5 border-t border-line/40 pt-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
        {label}
      </span>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 font-mono text-xs">{children}</dl>
    </section>
  );
}

function UtilizationBar({
  ratio,
  intent,
  used,
  max,
}: {
  ratio: number;
  intent: Intent;
  used: number;
  max: number;
}) {
  const clamped = !Number.isFinite(ratio) ? 0 : Math.max(0, Math.min(1, ratio));
  const widthPct = Math.max(2, clamped * 100);
  const colorClass =
    intent === "danger"
      ? "bg-danger"
      : intent === "warning"
        ? "bg-warning"
        : intent === "success"
          ? "bg-success"
          : intent === "accent"
            ? "bg-accent"
            : "bg-muted";
  return (
    <div
      role="meter"
      aria-valuemin={0}
      aria-valuemax={max > 0 ? max : 100}
      aria-valuenow={used}
      aria-label={`Utilization ${formatPercent(ratio)}`}
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

// ── Section building blocks (mirror QueuesPage) ──────────────────────────

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

// ── Status derivation ────────────────────────────────────────────────────

type SemaphoreStatus = "idle" | "active" | "contended" | "critical" | "saturated";

const STATUS_LABEL: Record<SemaphoreStatus, string> = {
  idle: "IDLE",
  active: "ACTIVE",
  contended: "CONTENDED",
  critical: "CRITICAL",
  saturated: "SATURATED",
};

const STATUS_INTENT: Record<SemaphoreStatus, Intent> = {
  idle: "success",
  active: "accent",
  contended: "warning",
  critical: "danger",
  saturated: "warning",
};

function deriveStatus(view: SemaphoreContentionView): SemaphoreStatus {
  if (view.severity === "saturated") return "saturated";
  if (view.severity === "critical") return "critical";
  if (view.severity === "warning") return "contended";
  // calm — distinguish idle (no permits in use) from active (some in use)
  if (view.utilizationRatio > 0 || view.permitsInUse > 0) return "active";
  return "idle";
}

// ── Formatters ────────────────────────────────────────────────────────────

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const clamped = Math.max(0, Math.min(1, value));
  return `${Math.round(clamped * 100)}%`;
}

function formatSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds === 0) return "0s";
  if (seconds < 1e-3) return `${(seconds * 1e6).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1e3).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m${remainder.toFixed(0).padStart(2, "0")}s`;
}

function formatPermits(used: number, max: number): string {
  if (max > 0) return `${used} / ${max}`;
  return `${used}`;
}

function formatBound(boundValue: number | null, initialValue: number): string {
  if (boundValue !== null && boundValue !== initialValue) return String(boundValue);
  if (boundValue === null) return "unbounded";
  return String(boundValue);
}
