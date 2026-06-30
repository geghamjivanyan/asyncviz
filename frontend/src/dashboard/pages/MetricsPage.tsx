/**
 * Aggregate analytics dashboard.
 *
 * Reads the canonical :type:`RuntimeMetricsAggregateSnapshot` already
 * folded into the runtime store by the hydration pipeline — no
 * additional fetching, no websocket subscriptions, no new contracts.
 * The page is a pure presentation layer over what the store carries.
 */

import { useMemo } from "react";
import { useMetricsAggregate } from "@/state/runtime";
import { Card } from "@/ui/primitives/Card";
import { Badge } from "@/ui/primitives/Badge";
import { cn } from "@/lib/cn";
import { formatDuration, formatWallTime } from "@/dashboard/inspector/utils/formatting";
import { formatCount, formatRate, formatUptime } from "@/dashboard/metrics/utils/format";
import type {
  AggregatorSelfMetricsModel,
  CoroutineRowModel,
  DurationStatsModel,
  DurationsByStateModel,
  LineageMetricsModel,
  RuntimeMetricsAggregateSnapshot,
  ThroughputModel,
  TopTaskModel,
} from "@/types/runtime";
import type { Intent } from "@/ui/theme/tokens";

export function MetricsPage() {
  const aggregate = useMetricsAggregate();
  return (
    <div
      data-metrics-page="true"
      className="flex h-full min-h-0 w-full min-w-0 flex-col gap-4 overflow-y-auto px-4 py-4"
    >
      <RuntimeSummarySection aggregate={aggregate} />
      <DurationStatisticsSection durations={aggregate?.durations ?? null} />
      <TopCoroutinesSection coroutines={aggregate?.coroutines ?? null} />
      <TopTasksSection title="Longest tasks" tasks={aggregate?.longest_tasks ?? null} />
      <TopTasksSection title="Shortest tasks" tasks={aggregate?.shortest_tasks ?? null} />
      <RuntimeTopologySection lineage={aggregate?.lineage ?? null} />
      <CancellationOriginsSection origins={aggregate?.cancellations_by_origin ?? null} />
      <AggregatorSelfMetricsSection selfMetrics={aggregate?.self_metrics ?? null} />
    </div>
  );
}

// ── Section 1 — Runtime Summary ───────────────────────────────────────────

function RuntimeSummarySection({
  aggregate,
}: {
  aggregate: RuntimeMetricsAggregateSnapshot | null;
}) {
  return (
    <Section title="Runtime summary">
      {aggregate === null ? (
        <SectionEmpty />
      ) : (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
          <SummaryCell label="Total tasks" value={formatCount(aggregate.counts.total)} />
          <SummaryCell label="Completed" value={formatCount(aggregate.counts.completed)} />
          <SummaryCell
            label="Failed"
            value={formatCount(aggregate.counts.failed)}
            intent={aggregate.counts.failed > 0 ? "danger" : "default"}
          />
          <SummaryCell
            label="Cancelled"
            value={formatCount(aggregate.counts.cancelled)}
            intent={aggregate.counts.cancelled > 0 ? "warning" : "default"}
          />
          <SummaryCell
            label="Runtime uptime"
            value={formatUptime(aggregate.runtime_uptime_seconds)}
          />
          <SummaryCell
            label="Throughput"
            value={formatRate(aggregate.throughput.tasks_per_second)}
            sub={throughputWindowLabel(aggregate.throughput)}
          />
          <SummaryCell
            label="Last aggregate"
            value={formatWallTime(aggregate.generated_at)}
          />
        </div>
      )}
    </Section>
  );
}

function throughputWindowLabel(throughput: ThroughputModel): string {
  if (!Number.isFinite(throughput.window_seconds) || throughput.window_seconds <= 0) {
    return "—";
  }
  return `over ${formatUptime(throughput.window_seconds)} window`;
}

// ── Section 2 — Duration Statistics ───────────────────────────────────────

function DurationStatisticsSection({
  durations,
}: {
  durations: DurationsByStateModel | null;
}) {
  if (durations === null) {
    return (
      <Section title="Duration statistics">
        <SectionEmpty />
      </Section>
    );
  }
  const buckets: { key: string; label: string; intent: Intent; stats: DurationStatsModel }[] = [
    { key: "completed", label: "Completed", intent: "success", stats: durations.completed },
    { key: "cancelled", label: "Cancelled", intent: "warning", stats: durations.cancelled },
    { key: "failed", label: "Failed", intent: "danger", stats: durations.failed },
    { key: "overall", label: "Overall", intent: "default", stats: durations.overall },
  ];
  const anyHasSamples = buckets.some((b) => b.stats.count > 0);
  if (!anyHasSamples) {
    return (
      <Section title="Duration statistics">
        <SectionEmpty />
      </Section>
    );
  }
  return (
    <Section title="Duration statistics">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
        {buckets.map((b) => (
          <DurationBucketCard key={b.key} label={b.label} intent={b.intent} stats={b.stats} />
        ))}
      </div>
    </Section>
  );
}

function DurationBucketCard({
  label,
  intent,
  stats,
}: {
  label: string;
  intent: Intent;
  stats: DurationStatsModel;
}) {
  const empty = stats.count === 0;
  return (
    <Card padding="sm" intent={empty ? "default" : intent} className="flex flex-col gap-2">
      <header className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</span>
        <Badge intent={empty ? "default" : intent}>{formatCount(stats.count)}</Badge>
      </header>
      {empty ? (
        <span className="font-mono text-xs text-subtle">No samples</span>
      ) : (
        <dl className="grid grid-cols-3 gap-x-3 gap-y-1 font-mono text-xs tabular-nums">
          <Stat label="Mean" value={formatDuration(stats.mean_seconds)} />
          <Stat label="Median" value={formatDuration(stats.histogram.p50)} />
          <Stat label="P95" value={formatDuration(stats.histogram.p95)} />
          <Stat label="P99" value={formatDuration(stats.histogram.p99)} />
          <Stat label="Min" value={formatDuration(stats.min_seconds)} />
          <Stat label="Max" value={formatDuration(stats.max_seconds)} />
        </dl>
      )}
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-[10px] uppercase tracking-widest text-subtle">{label}</dt>
      <dd className="text-text">{value}</dd>
    </div>
  );
}

// ── Section 3 — Top Coroutines ────────────────────────────────────────────

function TopCoroutinesSection({ coroutines }: { coroutines: CoroutineRowModel[] | null }) {
  const rows = useMemo(() => {
    if (coroutines === null || coroutines.length === 0) return [];
    return coroutines
      .slice()
      .sort(
        (a, b) =>
          (b.completed_total_duration_seconds ?? 0) - (a.completed_total_duration_seconds ?? 0),
      );
  }, [coroutines]);
  return (
    <Section title="Top coroutines">
      {rows.length === 0 ? (
        <SectionEmpty />
      ) : (
        <DataTable
          headers={["Coroutine", "Calls", "Total runtime", "Avg runtime", "Max runtime"]}
          align={["left", "right", "right", "right", "right"]}
          gridTemplate="minmax(12rem,2fr) 4rem 7rem 7rem 7rem"
          rows={rows.map((row) => ({
            key: row.coroutine_name,
            cells: [
              <Mono key="name" className="truncate">
                {row.coroutine_name}
              </Mono>,
              formatCount(row.task_count),
              formatDuration(row.completed_total_duration_seconds),
              formatDuration(row.completed_avg_duration_seconds),
              formatDuration(row.max_duration_seconds),
            ],
          }))}
        />
      )}
    </Section>
  );
}

// ── Sections 4 & 5 — Longest / Shortest Tasks ─────────────────────────────

function TopTasksSection({
  title,
  tasks,
}: {
  title: string;
  tasks: TopTaskModel[] | null;
}) {
  const rows = tasks ?? [];
  return (
    <Section title={title}>
      {rows.length === 0 ? (
        <SectionEmpty />
      ) : (
        <DataTable
          headers={["Task", "Coroutine", "Duration", "Final state"]}
          align={["left", "left", "right", "left"]}
          gridTemplate="minmax(10rem,1.5fr) minmax(10rem,1.5fr) 7rem 6.5rem"
          rows={rows.map((task) => ({
            key: task.task_id,
            cells: [
              <Mono key="task" className="truncate">
                {task.task_name ?? task.task_id}
              </Mono>,
              <Mono key="coroutine" className="truncate text-muted">
                {task.coroutine_name ?? "—"}
              </Mono>,
              formatDuration(task.duration_seconds),
              <Badge key="state" intent={stateIntent(task.state)}>
                {task.state}
              </Badge>,
            ],
          }))}
        />
      )}
    </Section>
  );
}

function stateIntent(state: string): Intent {
  switch (state) {
    case "completed":
      return "success";
    case "failed":
      return "danger";
    case "cancelled":
      return "warning";
    case "running":
      return "accent";
    case "waiting":
      return "accent";
    default:
      return "default";
  }
}

// ── Section 6 — Runtime Topology ──────────────────────────────────────────

function RuntimeTopologySection({ lineage }: { lineage: LineageMetricsModel | null }) {
  if (lineage === null) {
    return (
      <Section title="Runtime topology">
        <SectionEmpty />
      </Section>
    );
  }
  const hasAny =
    lineage.max_depth > 0 ||
    lineage.largest_tree_size > 0 ||
    lineage.root_count > 0 ||
    lineage.average_fanout > 0;
  if (!hasAny) {
    return (
      <Section title="Runtime topology">
        <SectionEmpty />
      </Section>
    );
  }
  return (
    <Section title="Runtime topology">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCell label="Maximum depth" value={formatCount(lineage.max_depth)} />
        <SummaryCell
          label="Largest task tree"
          value={formatCount(lineage.largest_tree_size)}
          sub={
            lineage.largest_tree_root_id !== null
              ? `root ${shortId(lineage.largest_tree_root_id)}`
              : undefined
          }
        />
        <SummaryCell
          label="Average fan-out"
          value={
            Number.isFinite(lineage.average_fanout)
              ? lineage.average_fanout.toFixed(2)
              : "—"
          }
          sub={`${formatCount(lineage.root_count)} roots`}
        />
        <SummaryCell
          label="Cancellations propagated"
          value={formatCount(lineage.cancellations_propagated)}
          intent={lineage.cancellations_propagated > 0 ? "warning" : "default"}
        />
      </div>
    </Section>
  );
}

function shortId(id: string): string {
  if (id.length <= 12) return id;
  return `${id.slice(0, 6)}…${id.slice(-4)}`;
}

// ── Section 7 — Cancellation Origins ──────────────────────────────────────

function CancellationOriginsSection({
  origins,
}: {
  origins: Record<string, number> | null;
}) {
  const entries = useMemo(() => {
    if (origins === null) return [];
    return Object.entries(origins)
      .filter(([, count]) => Number.isFinite(count) && count > 0)
      .sort((a, b) => b[1] - a[1]);
  }, [origins]);
  const max = entries.length > 0 ? Math.max(...entries.map(([, c]) => c)) : 0;
  return (
    <Section title="Cancellation origins">
      {entries.length === 0 ? (
        <SectionEmpty />
      ) : (
        <Card padding="sm">
          <ul className="flex flex-col gap-2">
            {entries.map(([origin, count]) => {
              const pct = max > 0 ? count / max : 0;
              return (
                <li key={origin} className="flex items-center gap-3 font-mono text-xs">
                  <span className="w-32 shrink-0 truncate uppercase tracking-wider text-muted">
                    {origin}
                  </span>
                  <div className="relative h-2 flex-1 overflow-hidden rounded bg-elevated">
                    <div
                      className="h-full bg-warning"
                      style={{ width: `${Math.max(2, pct * 100).toFixed(1)}%` }}
                      aria-hidden="true"
                    />
                  </div>
                  <span className="w-12 shrink-0 text-right tabular-nums text-text">
                    {formatCount(count)}
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </Section>
  );
}

// ── Section 8 — Aggregator Self Metrics ───────────────────────────────────

function AggregatorSelfMetricsSection({
  selfMetrics,
}: {
  selfMetrics: AggregatorSelfMetricsModel | null;
}) {
  if (selfMetrics === null) {
    return (
      <Section title="Aggregator self metrics">
        <SectionEmpty />
      </Section>
    );
  }
  const cells: { label: string; value: string; intent?: Intent }[] = [
    { label: "Events observed", value: formatCount(selfMetrics.events_observed) },
    {
      label: "Events stale",
      value: formatCount(selfMetrics.events_stale),
      intent: selfMetrics.events_stale > 0 ? "warning" : undefined,
    },
    {
      label: "Events duplicate",
      value: formatCount(selfMetrics.events_duplicate),
      intent: selfMetrics.events_duplicate > 0 ? "warning" : undefined,
    },
    { label: "Snapshots emitted", value: formatCount(selfMetrics.snapshots_emitted) },
    { label: "Rebuilds completed", value: formatCount(selfMetrics.rebuilds_completed) },
    {
      label: "Subscription dispatches",
      value: formatCount(selfMetrics.subscription_dispatches),
    },
    {
      label: "Subscription failures",
      value: formatCount(selfMetrics.subscription_failures),
      intent: selfMetrics.subscription_failures > 0 ? "danger" : undefined,
    },
    { label: "Last event sequence", value: formatCount(selfMetrics.last_event_sequence) },
  ];
  return (
    <Section title="Aggregator self metrics">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-4">
        {cells.map((cell) => (
          <SummaryCell
            key={cell.label}
            label={cell.label}
            value={cell.value}
            intent={cell.intent}
          />
        ))}
      </div>
    </Section>
  );
}

// ── Shared building blocks ───────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <header className="flex items-baseline justify-between">
        <h2 className="font-mono text-[10px] uppercase tracking-widest text-muted">{title}</h2>
      </header>
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
        <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">{sub}</span>
      )}
    </Card>
  );
}

// ── Data table primitive ─────────────────────────────────────────────────

interface DataTableProps {
  headers: readonly string[];
  align: readonly ("left" | "right")[];
  gridTemplate: string;
  rows: readonly { key: string; cells: readonly React.ReactNode[] }[];
}

function DataTable({ headers, align, gridTemplate, rows }: DataTableProps) {
  return (
    <Card padding="none" className="overflow-hidden">
      <div role="table" className="flex flex-col font-mono text-xs">
        <div
          role="row"
          style={{ gridTemplateColumns: gridTemplate }}
          className="grid h-8 items-center gap-3 border-b border-line bg-elevated px-3 text-[10px] uppercase tracking-widest text-muted"
        >
          {headers.map((header, i) => (
            <div
              key={header}
              role="columnheader"
              className={cn(
                "truncate",
                align[i] === "right" ? "text-right" : "text-left",
              )}
            >
              {header}
            </div>
          ))}
        </div>
        {rows.map((row, rowIndex) => (
          <div
            key={row.key}
            role="row"
            style={{ gridTemplateColumns: gridTemplate }}
            className={cn(
              "grid items-center gap-3 px-3 py-1.5 text-text",
              rowIndex !== rows.length - 1 && "border-b border-line/60",
            )}
          >
            {row.cells.map((cell, i) => (
              <div
                key={i}
                role="cell"
                className={cn(
                  "min-w-0 truncate tabular-nums",
                  align[i] === "right" ? "text-right" : "text-left",
                )}
              >
                {cell}
              </div>
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}

function Mono({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <span className={cn("font-mono text-text", className)}>{children}</span>;
}
