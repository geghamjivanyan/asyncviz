/**
 * Executor activity dashboard.
 *
 * Presentation-only surface over the data the existing executor store
 * already provides: ``useExecutorRecords`` + ``useExecutorActivityViewsBySeverity``
 * for the projected views, plus the existing hydration + websocket
 * bridge hooks. No backend or schema changes — every number on the
 * page reads from data that was already flowing.
 */

import { useEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/cn";
import { Card } from "@/ui/primitives/Card";
import { Badge } from "@/ui/primitives/Badge";
import { EmptyState } from "@/ui/feedback/EmptyState";
import type { Intent } from "@/ui/theme/tokens";
import { useExecutorActivityHydration } from "@/dashboard/executors/hooks/useExecutorActivityHydration";
import { useExecutorActivityWebsocketBridge } from "@/dashboard/executors/hooks/useExecutorActivityWebsocketBridge";
import { useExecutorActivitySelection } from "@/dashboard/executors/hooks/useExecutorActivitySelection";
import {
  useExecutorActivityErrorMessage,
  useExecutorActivityMarkers,
  useExecutorActivityStatus,
  useExecutorActivityViewsBySeverity,
  useExecutorRecords,
} from "@/dashboard/executors/selectors/ExecutorActivitySelectors";
import { ExecutorActivityTimeline } from "@/dashboard/executors/ExecutorActivityTimeline";
import type {
  ExecutorActivityView,
  ExecutorMetricsRecord,
} from "@/dashboard/executors/models/ExecutorActivityModels";

export function ExecutorsPage(): JSX.Element {
  useExecutorActivityHydration({ enabled: true });
  useExecutorActivityWebsocketBridge({ enabled: true });

  const views = useExecutorActivityViewsBySeverity();
  const records = useExecutorRecords();
  const { selectedExecutorId, selectExecutor } = useExecutorActivitySelection();
  const status = useExecutorActivityStatus();
  const errorMessage = useExecutorActivityErrorMessage();
  const markers = useExecutorActivityMarkers();

  // Record lookup by id — cards need ``ExecutorLatencyRecord.max_seconds``
  // (not on the projected view) for "Peak execution" + "Peak wait".
  const recordsById = useMemo(() => {
    const m = new Map<string, ExecutorMetricsRecord>();
    for (const r of records) m.set(r.executor_id, r);
    return m;
  }, [records]);

  // Session-max backlog per executor. ``backlog`` only carries the
  // current depth on the wire — tracking the peak across the page's
  // lifetime is a derived observation, not a fabricated metric.
  const peakBacklogRef = useRef<Map<string, number>>(new Map());
  useEffect(() => {
    const peaks = peakBacklogRef.current;
    for (const record of records) {
      const prev = peaks.get(record.executor_id) ?? 0;
      if (record.throughput.backlog > prev) {
        peaks.set(record.executor_id, record.throughput.backlog);
      }
    }
  }, [records]);

  const summary = useMemo(
    () => buildSummary(views, recordsById, peakBacklogRef.current),
    [views, recordsById],
  );
  const selectedView = useMemo<ExecutorActivityView | null>(
    () =>
      selectedExecutorId === null
        ? null
        : (views.find((v) => v.executorId === selectedExecutorId) ?? null),
    [views, selectedExecutorId],
  );

  // When the runtime exposes exactly one executor, select it
  // automatically so the inspector lands populated. We don't refresh
  // the selection on subsequent renders — once a user clicks Clear or
  // selects another executor we respect their choice.
  const autoSelectedOnceRef = useRef(false);
  useEffect(() => {
    if (autoSelectedOnceRef.current) return;
    if (selectedExecutorId !== null) {
      autoSelectedOnceRef.current = true;
      return;
    }
    if (views.length === 1) {
      autoSelectedOnceRef.current = true;
      selectExecutor(views[0]!.executorId);
    }
  }, [views, selectedExecutorId, selectExecutor]);
  const selectedRecord =
    selectedExecutorId !== null ? (recordsById.get(selectedExecutorId) ?? null) : null;

  const hasExecutors = views.length > 0;
  const isLoading = status === "loading" && !hasExecutors;
  const isError = status === "error";

  return (
    <div
      data-executors-page="true"
      className="flex h-full min-h-0 w-full min-w-0 flex-col gap-4 overflow-y-auto px-4 py-4"
    >
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-mono text-sm uppercase tracking-widest text-text">Executors</h1>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {summary.total} tracked
          </span>
        </div>
        {isError && (
          <Badge intent="danger" role="alert">
            {errorMessage ?? "Failed to load executor metrics"}
          </Badge>
        )}
        {isLoading && (
          <Badge intent="accent" aria-live="polite">
            Loading
          </Badge>
        )}
      </header>

      <Section title="Executor summary">
        {hasExecutors ? (
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(11rem, 1fr))" }}
          >
            <SummaryCell label="Total executors" value={String(summary.total)} />
            <SummaryCell
              label="Busy"
              value={String(summary.busy)}
              intent={summary.busy > 0 ? "accent" : "default"}
            />
            <SummaryCell
              label="Idle"
              value={String(summary.idle)}
              intent={summary.idle > 0 ? "success" : "default"}
            />
            <SummaryCell label="Total workers" value={String(summary.totalWorkers)} />
            <SummaryCell
              label="Avg utilization"
              value={formatPercent(summary.avgUtilization)}
              intent={summary.avgUtilization >= 0.85 ? "warning" : "default"}
            />
            <SummaryCell
              label="Peak queue"
              value={String(summary.peakBacklog)}
              sub={summary.peakBacklogName ?? undefined}
              intent={summary.peakBacklog > 0 ? "warning" : "default"}
            />
            <SummaryCell label="Avg queue wait" value={formatSeconds(summary.avgQueueWait)} />
            <SummaryCell
              label="Peak execution"
              value={formatSeconds(summary.peakExecution)}
              sub={summary.peakExecutionName ?? undefined}
              intent={summary.peakExecution >= 1 ? "warning" : "default"}
            />
          </div>
        ) : (
          <SectionEmpty />
        )}
      </Section>

      <Section title="Executor timeline">
        <Card padding="sm" className="flex min-h-[7rem] flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Saturation + contention markers
            </span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
              {markers.length} marker{markers.length === 1 ? "" : "s"}
            </span>
          </div>
          {markers.length > 0 ? (
            <ExecutorActivityTimeline markers={markers} heightPx={40} />
          ) : (
            <div className="flex flex-1 items-center justify-center px-6 py-3 text-center">
              <p className="font-mono text-xs text-subtle">
                No historical executor samples available.
              </p>
            </div>
          )}
        </Card>
      </Section>

      <Section title="Executors">
        <div className="flex min-h-0 flex-1 gap-2">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            {hasExecutors ? (
              <div
                className="grid gap-2"
                style={{ gridTemplateColumns: "repeat(auto-fit, minmax(24rem, 1fr))" }}
              >
                {views.map((view) => (
                  <ExecutorCard
                    key={view.executorId}
                    view={view}
                    record={recordsById.get(view.executorId) ?? null}
                    peakBacklog={peakBacklogRef.current.get(view.executorId) ?? 0}
                    selected={view.executorId === selectedExecutorId}
                    onSelect={selectExecutor}
                  />
                ))}
              </div>
            ) : isLoading ? (
              <SectionEmpty />
            ) : (
              <EmptyState
                title="No executors observed."
                description="Executor activity appears here as soon as your runtime submits work via loop.run_in_executor, asyncio.to_thread, or a ThreadPool / ProcessPoolExecutor."
              />
            )}
          </div>
          {hasExecutors && (
            <aside
              aria-label="Executor inspector"
              className="hidden h-full w-[340px] shrink-0 overflow-y-auto md:flex"
            >
              <ExecutorInspector
                view={selectedView}
                record={selectedRecord}
                peakBacklog={
                  selectedExecutorId ? (peakBacklogRef.current.get(selectedExecutorId) ?? 0) : 0
                }
                onClear={() => selectExecutor(null)}
              />
            </aside>
          )}
        </div>
      </Section>
    </div>
  );
}

// ── Summary projection ───────────────────────────────────────────────────

interface ExecutorSummary {
  total: number;
  busy: number;
  idle: number;
  totalWorkers: number;
  avgUtilization: number;
  peakBacklog: number;
  peakBacklogName: string | null;
  avgQueueWait: number;
  peakExecution: number;
  peakExecutionName: string | null;
}

function buildSummary(
  views: readonly ExecutorActivityView[],
  recordsById: Map<string, ExecutorMetricsRecord>,
  sessionPeaks: Map<string, number>,
): ExecutorSummary {
  if (views.length === 0) {
    return {
      total: 0,
      busy: 0,
      idle: 0,
      totalWorkers: 0,
      avgUtilization: 0,
      peakBacklog: 0,
      peakBacklogName: null,
      avgQueueWait: 0,
      peakExecution: 0,
      peakExecutionName: null,
    };
  }
  let busy = 0;
  let idle = 0;
  let totalWorkers = 0;
  let utilizationSum = 0;
  let queueWaitSum = 0;
  let queueWaitCount = 0;
  let peakBacklog = 0;
  let peakBacklogName: string | null = null;
  let peakExecution = 0;
  let peakExecutionName: string | null = null;
  for (const view of views) {
    if (view.activeWorkers > 0) busy += 1;
    else idle += 1;
    totalWorkers += view.maxWorkers ?? view.peakActiveWorkers;
    if (Number.isFinite(view.utilizationRatio)) utilizationSum += view.utilizationRatio;
    const sessionPeak = sessionPeaks.get(view.executorId) ?? 0;
    if (sessionPeak > peakBacklog) {
      peakBacklog = sessionPeak;
      peakBacklogName = view.displayName;
    }
    if (Number.isFinite(view.meanSubmissionLatencySeconds)) {
      queueWaitSum += view.meanSubmissionLatencySeconds;
      queueWaitCount += 1;
    }
    const record = recordsById.get(view.executorId);
    const execMax = record?.execution_duration.max_seconds ?? 0;
    if (Number.isFinite(execMax) && execMax > peakExecution) {
      peakExecution = execMax;
      peakExecutionName = view.displayName;
    }
  }
  return {
    total: views.length,
    busy,
    idle,
    totalWorkers,
    avgUtilization: utilizationSum / views.length,
    peakBacklog,
    peakBacklogName,
    avgQueueWait: queueWaitCount > 0 ? queueWaitSum / queueWaitCount : 0,
    peakExecution,
    peakExecutionName,
  };
}

// ── Executor card ────────────────────────────────────────────────────────

interface ExecutorCardProps {
  view: ExecutorActivityView;
  record: ExecutorMetricsRecord | null;
  peakBacklog: number;
  selected: boolean;
  onSelect: (id: string | null) => void;
}

function ExecutorCard({
  view,
  record,
  peakBacklog,
  selected,
  onSelect,
}: ExecutorCardProps): JSX.Element {
  const status = deriveStatus(view);
  const intent = STATUS_INTENT[status];
  const utilization = clampRatio(view.utilizationRatio);
  const maxWorkers = view.maxWorkers ?? view.peakActiveWorkers;
  const idleWorkers =
    maxWorkers != null && Number.isFinite(maxWorkers)
      ? Math.max(0, maxWorkers - view.activeWorkers)
      : null;
  const peakSubmission = record?.submission_latency.max_seconds ?? null;
  const peakExecution = record?.execution_duration.max_seconds ?? null;

  return (
    <Card
      padding="sm"
      intent={intent}
      className={cn("flex flex-col gap-4 transition-colors", selected ? "ring-1 ring-accent" : "")}
      data-executor-id={view.executorId}
      data-severity={view.severity}
      data-status={status}
      data-selected={selected ? "true" : undefined}
    >
      <header className="flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => onSelect(selected ? null : view.executorId)}
          className="flex min-w-0 flex-col items-start gap-0.5 text-left"
          aria-pressed={selected}
        >
          <span className="truncate font-mono text-sm text-text">{view.displayName}</span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {view.executorKind}
          </span>
        </button>
        <Badge intent={intent} aria-label={`Status ${STATUS_LABEL[status]}`}>
          {STATUS_LABEL[status]}
        </Badge>
      </header>

      {/* Utilization */}
      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3 font-mono">
          <span className="text-[10px] uppercase tracking-widest text-muted">Utilization</span>
          <span className="flex items-baseline gap-3">
            <span
              className={cn(
                "text-sm tabular-nums",
                utilization >= 0.999 ? "text-warning" : "text-text",
              )}
            >
              {formatPercent(utilization)}
            </span>
            <span className="text-[10px] uppercase tracking-widest text-subtle">
              {view.activeWorkers} / {maxWorkers ?? "?"} workers
            </span>
          </span>
        </div>
        <ProgressBar ratio={utilization} intent={intent} />
        <WorkerSquares maxWorkers={maxWorkers} activeWorkers={view.activeWorkers} intent={intent} />
      </section>

      {/* Queue */}
      <MetricGroup label="Queue">
        <QueueVisualization
          current={view.backlog}
          peak={peakBacklog}
          capacity={maxWorkers ?? null}
          intent={intent}
        />
      </MetricGroup>

      {/* Workers */}
      <MetricGroup label="Workers">
        <Metric label="Total" value={String(maxWorkers ?? "—")} />
        <Metric
          label="Busy"
          value={String(view.activeWorkers)}
          intent={view.activeWorkers > 0 ? "accent" : undefined}
        />
        <Metric
          label="Idle"
          value={idleWorkers === null ? "—" : String(idleWorkers)}
          intent={idleWorkers !== null && idleWorkers > 0 ? "success" : undefined}
        />
        <Metric label="Peak active" value={String(view.peakActiveWorkers)} />
      </MetricGroup>

      {/* Throughput */}
      <MetricGroup label="Throughput">
        <Metric label="Submitted/sec" value={formatRate(view.submissionRate)} />
        <Metric label="Completed/sec" value={formatRate(view.completionRate)} />
      </MetricGroup>

      {/* Latency */}
      <MetricGroup label="Latency">
        <Metric label="Avg queue wait" value={formatSeconds(view.meanSubmissionLatencySeconds)} />
        <Metric
          label="P95 queue wait"
          value={formatSeconds(view.p95SubmissionLatencySeconds)}
          intent={view.p95SubmissionLatencySeconds >= 1 ? "warning" : undefined}
        />
        <Metric label="Avg execution" value={formatSeconds(view.meanExecutionDurationSeconds)} />
        <Metric
          label="P95 execution"
          value={formatSeconds(view.p95ExecutionDurationSeconds)}
          intent={view.p95ExecutionDurationSeconds >= 1 ? "warning" : undefined}
        />
        <Metric label="Peak wait" value={formatSeconds(peakSubmission ?? Number.NaN)} />
        <Metric
          label="Peak execution"
          value={formatSeconds(peakExecution ?? Number.NaN)}
          intent={peakExecution !== null && peakExecution >= 1 ? "danger" : undefined}
        />
      </MetricGroup>

      {/* Operations */}
      <MetricGroup label="Operations">
        <Metric label="Submitted" value={String(view.submissions)} />
        <Metric label="Completed" value={String(view.completions)} />
        <Metric
          label="Cancelled"
          value={String(view.cancellations)}
          intent={view.cancellations > 0 ? "warning" : undefined}
        />
        <Metric
          label="Failures"
          value={String(view.failures)}
          intent={view.failures > 0 ? "danger" : undefined}
        />
      </MetricGroup>
    </Card>
  );
}

function ProgressBar({ ratio, intent }: { ratio: number; intent: Intent }) {
  const widthPct = Math.max(2, ratio * 100);
  const color =
    intent === "danger"
      ? "bg-danger"
      : intent === "warning"
        ? "bg-warning"
        : intent === "accent"
          ? "bg-accent"
          : intent === "success"
            ? "bg-success"
            : "bg-muted";
  return (
    <div
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(ratio * 100)}
      aria-label={`Utilization ${formatPercent(ratio)}`}
      className="relative h-1.5 w-full overflow-hidden rounded bg-elevated"
    >
      <div
        className={cn("h-full", color)}
        style={{ width: `${widthPct.toFixed(1)}%` }}
        aria-hidden="true"
      />
    </div>
  );
}

function WorkerSquares({
  maxWorkers,
  activeWorkers,
  intent,
}: {
  maxWorkers: number | null | undefined;
  activeWorkers: number;
  intent: Intent;
}) {
  // Backend exposes only worker counts, not per-worker state — when
  // ``max_workers`` is missing we can't even draw a worker grid. Tell
  // the user explicitly instead of leaving a blank line.
  if (!maxWorkers || !Number.isFinite(maxWorkers) || maxWorkers <= 0) {
    return (
      <p
        className="font-mono text-[10px] uppercase tracking-widest text-subtle"
        title="Per-worker state is not exposed by the runtime; the utilization bar above reflects the available signal."
      >
        Per-worker state unavailable
      </p>
    );
  }
  const MAX_SQUARES = 32;
  const displayed = Math.min(maxWorkers, MAX_SQUARES);
  const overflow = maxWorkers - displayed;
  const busyColor =
    intent === "danger" ? "bg-danger" : intent === "warning" ? "bg-warning" : "bg-accent";
  const displayedBusy =
    maxWorkers <= MAX_SQUARES
      ? activeWorkers
      : Math.round((activeWorkers / maxWorkers) * displayed);
  const squares: JSX.Element[] = [];
  for (let i = 0; i < displayed; i += 1) {
    const isBusy = i < displayedBusy;
    squares.push(
      <span
        key={i}
        title={isBusy ? "Busy worker" : "Idle worker"}
        className={cn(
          "h-2.5 w-2.5 rounded-sm border border-line/60",
          isBusy ? busyColor : "bg-success/40",
        )}
        aria-hidden="true"
      />,
    );
  }
  return (
    <div
      className="flex flex-wrap items-center gap-1"
      data-worker-grid="true"
      title={`${activeWorkers} busy / ${maxWorkers - activeWorkers} idle`}
    >
      {squares}
      {overflow > 0 && (
        <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
          +{overflow}
        </span>
      )}
    </div>
  );
}

function QueueVisualization({
  current,
  peak,
  capacity,
  intent,
}: {
  current: number;
  peak: number;
  capacity: number | null;
  intent: Intent;
}) {
  const slots = 18;
  // Reference for the bar fill: the largest of (capacity, session
  // peak, current). Without that we'd flatten ratios as soon as the
  // queue grew beyond the peak.
  const reference = Math.max(capacity ?? 0, peak, current, 1);
  const filled = Math.min(slots, Math.round((current / reference) * slots));
  const fillColor =
    intent === "danger"
      ? "bg-danger"
      : intent === "warning"
        ? "bg-warning"
        : intent === "accent"
          ? "bg-accent"
          : "bg-success";
  const cells: JSX.Element[] = [];
  for (let i = 0; i < slots; i += 1) {
    cells.push(
      <span
        key={i}
        className={cn(
          "h-3 flex-1 rounded-sm border border-line/60",
          i < filled ? fillColor : "bg-elevated",
        )}
        aria-hidden="true"
      />,
    );
  }
  const denominator = capacity ?? peak;
  return (
    <div className="col-span-2 flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3 font-mono">
        <span className="text-[10px] uppercase tracking-widest text-muted">Queue</span>
        <span className="flex items-baseline gap-3 tabular-nums">
          <span className="text-text">
            {current}
            {denominator > 0 ? ` / ${denominator}` : ""}
          </span>
          {peak > 0 && (
            <span className="text-[10px] uppercase tracking-widest text-subtle">peak {peak}</span>
          )}
        </span>
      </div>
      <div
        className="flex items-center gap-0.5"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={reference}
        aria-valuenow={current}
        aria-label={`Queue depth ${current} of ${reference}`}
      >
        {cells}
      </div>
    </div>
  );
}

function MetricGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5 border-t border-line/40 pt-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">{label}</span>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 font-mono text-xs">{children}</div>
    </section>
  );
}

function Metric({ label, value, intent }: { label: string; value: string; intent?: Intent }) {
  const valueColor =
    intent === "danger"
      ? "text-danger"
      : intent === "warning"
        ? "text-warning"
        : intent === "accent"
          ? "text-accent"
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

// ── Inspector ───────────────────────────────────────────────────────────

function ExecutorInspector({
  view,
  record,
  peakBacklog,
  onClear,
}: {
  view: ExecutorActivityView | null;
  record: ExecutorMetricsRecord | null;
  peakBacklog: number;
  onClear: () => void;
}): JSX.Element {
  if (view === null) {
    return (
      <Card padding="md" className="flex h-full w-full flex-col gap-3">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Inspector
        </span>
        <p className="font-mono text-xs leading-relaxed text-subtle">
          Click an executor to inspect its workers, queue, and latency.
        </p>
      </Card>
    );
  }
  const status = deriveStatus(view);
  const intent = STATUS_INTENT[status];
  const maxWorkers = view.maxWorkers ?? view.peakActiveWorkers;
  const idleWorkers =
    maxWorkers != null && Number.isFinite(maxWorkers)
      ? Math.max(0, maxWorkers - view.activeWorkers)
      : null;
  const peakSubmission = record?.submission_latency.max_seconds ?? null;
  const peakExecution = record?.execution_duration.max_seconds ?? null;

  return (
    <Card padding="md" className="flex h-full w-full flex-col gap-4">
      <header className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Inspector
          </span>
          <span className="truncate font-mono text-sm text-text">{view.displayName}</span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {view.executorKind}
          </span>
        </div>
        <button
          type="button"
          onClick={onClear}
          aria-label="Clear selection"
          title="Clear selection"
          className="shrink-0 rounded border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
        >
          Clear selection
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <Badge intent={intent}>{STATUS_LABEL[status]}</Badge>
        {view.severity !== "calm" && (
          <Badge intent={SEVERITY_INTENT[view.severity]}>{view.severity.toUpperCase()}</Badge>
        )}
      </div>

      <InspectorSection title="General">
        <InspectorKV label="Name" value={view.displayName} />
        <InspectorKV label="Type" value={view.executorKind} />
        <InspectorKV label="Status" value={STATUS_LABEL[status]} intent={intent} />
        <InspectorKV
          label="Saturation"
          value={view.saturationScore.toFixed(2)}
          intent={view.saturationScore >= 0.85 ? "warning" : undefined}
        />
      </InspectorSection>

      <InspectorSection title="Workers">
        <InspectorKV label="Total" value={String(maxWorkers ?? "—")} />
        <InspectorKV
          label="Busy"
          value={String(view.activeWorkers)}
          intent={view.activeWorkers > 0 ? "accent" : undefined}
        />
        <InspectorKV
          label="Idle"
          value={idleWorkers === null ? "—" : String(idleWorkers)}
          intent={idleWorkers !== null && idleWorkers > 0 ? "success" : undefined}
        />
        <InspectorKV
          label="Utilization"
          value={formatPercent(view.utilizationRatio)}
          intent={view.utilizationRatio >= 0.999 ? "warning" : undefined}
        />
        <InspectorKV label="Peak workers" value={String(view.peakActiveWorkers)} />
      </InspectorSection>

      <InspectorSection title="Queue">
        <InspectorKV label="Depth" value={String(view.backlog)} />
        <InspectorKV
          label="Peak depth"
          value={String(peakBacklog || view.backlog)}
          intent={peakBacklog > 0 ? "warning" : undefined}
        />
      </InspectorSection>

      <InspectorSection title="Latency">
        <InspectorKV label="Avg wait" value={formatSeconds(view.meanSubmissionLatencySeconds)} />
        <InspectorKV
          label="P95 wait"
          value={formatSeconds(view.p95SubmissionLatencySeconds)}
          intent={view.p95SubmissionLatencySeconds >= 1 ? "warning" : undefined}
        />
        <InspectorKV label="Peak wait" value={formatSeconds(peakSubmission ?? Number.NaN)} />
        <InspectorKV
          label="Avg execution"
          value={formatSeconds(view.meanExecutionDurationSeconds)}
        />
        <InspectorKV
          label="P95 execution"
          value={formatSeconds(view.p95ExecutionDurationSeconds)}
          intent={view.p95ExecutionDurationSeconds >= 1 ? "warning" : undefined}
        />
        <InspectorKV
          label="Peak execution"
          value={formatSeconds(peakExecution ?? Number.NaN)}
          intent={peakExecution !== null && peakExecution >= 1 ? "danger" : undefined}
        />
      </InspectorSection>

      <InspectorSection title="Operations">
        <InspectorKV label="Submitted" value={String(view.submissions)} />
        <InspectorKV label="Completed" value={String(view.completions)} />
        <InspectorKV
          label="Cancelled"
          value={String(view.cancellations)}
          intent={view.cancellations > 0 ? "warning" : undefined}
        />
        <InspectorKV
          label="Failures"
          value={String(view.failures)}
          intent={view.failures > 0 ? "danger" : undefined}
        />
      </InspectorSection>
    </Card>
  );
}

const SEVERITY_INTENT: Record<ExecutorActivityView["severity"], Intent> = {
  calm: "default",
  warning: "warning",
  critical: "danger",
  saturated: "warning",
};

function InspectorSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5 border-t border-line/40 pt-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">{title}</span>
      <div className="flex flex-col gap-1">{children}</div>
    </section>
  );
}

function InspectorKV({ label, value, intent }: { label: string; value: string; intent?: Intent }) {
  const valueColor =
    intent === "danger"
      ? "text-danger"
      : intent === "warning"
        ? "text-warning"
        : intent === "success"
          ? "text-success"
          : intent === "accent"
            ? "text-accent"
            : "text-text";
  return (
    <div className="flex items-baseline justify-between gap-3 font-mono text-xs">
      <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className={cn("tabular-nums", valueColor)}>{value}</span>
    </div>
  );
}

// ── Section building blocks ─────────────────────────────────────────────

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

// ── Status derivation ───────────────────────────────────────────────────

type ExecutorStatus = "idle" | "busy" | "contended" | "critical" | "saturated";

const STATUS_LABEL: Record<ExecutorStatus, string> = {
  idle: "IDLE",
  busy: "BUSY",
  contended: "CONTENDED",
  critical: "CRITICAL",
  saturated: "SATURATED",
};

const STATUS_INTENT: Record<ExecutorStatus, Intent> = {
  idle: "success",
  busy: "accent",
  contended: "warning",
  critical: "danger",
  saturated: "warning",
};

function deriveStatus(view: ExecutorActivityView): ExecutorStatus {
  if (view.severity === "saturated") return "saturated";
  if (view.severity === "critical") return "critical";
  if (view.severity === "warning") return "contended";
  if (view.activeWorkers > 0 || view.utilizationRatio > 0) return "busy";
  return "idle";
}

// ── Formatters ──────────────────────────────────────────────────────────

function clampRatio(value: number): number {
  if (!Number.isFinite(value) || value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return `${Math.round(clampRatio(value) * 100)}%`;
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

function formatRate(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0/s";
  if (value >= 100) return `${value.toFixed(0)}/s`;
  if (value >= 10) return `${value.toFixed(1)}/s`;
  return `${value.toFixed(2)}/s`;
}
