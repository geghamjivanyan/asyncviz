/**
 * Diagnostics page.
 *
 * Four-section hierarchy:
 *
 *   1. Runtime Diagnostics — high-level findings derived from live
 *      runtime state (queues, semaphores, executors, dependencies,
 *      blocking warnings, connection). Each finding explains the
 *      problem and proposes a fix.
 *   2. Recommendations — short actionable items folded out of the
 *      same signals.
 *   3. Runtime Summary — counts across every subsystem.
 *   4. Developer Diagnostics — the original internal counters (HMR,
 *      websocket envelope inflight, hydration counters, projection
 *      pipeline, etc.). Collapsed by default — the dashboard is for
 *      operators, not contributors, except when debugging the
 *      dashboard itself.
 */

import { useEffect, useMemo, useState, type JSX } from "react";
import { useClientMetrics } from "@/app/providers/RuntimeProvider";
import { useRuntimeConfig } from "@/app/providers/ConfigProvider";
import { Card } from "@/ui/primitives/Card";
import { Badge } from "@/ui/primitives/Badge";
import type { Intent } from "@/ui/theme/tokens";

import { useMetricsHeaderSnapshot } from "@/dashboard/metrics";
import { useQueuePressureViewsBundle } from "@/dashboard/queues";
import { useSemaphoreContentionViewsBundle } from "@/dashboard/semaphores";
import { useExecutorActivityViewsBundle } from "@/dashboard/executors";
import { useAwaitDependencyViews } from "@/dashboard/dependencies";
import { useBlockingWarningProjections } from "@/dashboard/warnings/blocking";

import { TaskDiagnostics } from "@/dashboard/tasks";
import { MetricsDiagnostics } from "@/dashboard/metrics";
import { RuntimeEventDiagnostics } from "@/dashboard/events";
import { ConnectionDiagnostics } from "@/dashboard/connection";
import { TimelineDiagnostics } from "@/dashboard/timeline";
import { BlockingWarningsDiagnostics } from "@/dashboard/warnings/blocking";
import { FreezeRegionDiagnostics } from "@/dashboard/timeline/freeze_regions";
import { QueuePressureDiagnostics } from "@/dashboard/queues";
import { SemaphoreContentionDiagnostics } from "@/dashboard/semaphores";
import { AwaitDependencyDiagnostics } from "@/dashboard/dependencies";
import { ExecutorActivityDiagnostics } from "@/dashboard/executors";

import {
  deriveRuntimeFindings,
  type RelatedRuntimeObject,
  type RuntimeFinding,
  type FindingSeverity,
} from "@/dashboard/diagnostics/RuntimeFindings";
import {
  deriveRuntimeRecommendations,
  type RuntimeRecommendation,
} from "@/dashboard/diagnostics/RuntimeRecommendations";

interface ClientStats {
  envelopesReceived: number;
  envelopesDropped: number;
  websocketConnectAttempts: number;
  websocketReconnects: number;
  websocketFailures: number;
  protocolMismatches: number;
  snapshotHydrations: number;
  snapshotHydrationFailures: number;
  renderErrors: number;
}

export function DiagnosticsPage(): JSX.Element {
  const config = useRuntimeConfig();
  const metrics = useClientMetrics();
  const [stats, setStats] = useState<ClientStats>(() => projectStats(metrics.snapshot()));

  useEffect(() => {
    const handle = window.setInterval(() => {
      setStats(projectStats(metrics.snapshot()));
    }, 1000);
    return () => window.clearInterval(handle);
  }, [metrics]);

  const header = useMetricsHeaderSnapshot();
  const queueBundle = useQueuePressureViewsBundle();
  const semaphoreBundle = useSemaphoreContentionViewsBundle();
  const executorBundle = useExecutorActivityViewsBundle();
  const dependencyViews = useAwaitDependencyViews();
  const blockingProjections = useBlockingWarningProjections();

  const findings = useMemo(
    () =>
      deriveRuntimeFindings({
        health: header.health,
        connection: header.connection,
        warnings: header.warnings,
        tasks: header.taskCounts,
        eventRate: header.eventRate,
        queues: queueBundle.views,
        semaphores: semaphoreBundle.views,
        executors: executorBundle.views,
        dependencyNodes: dependencyViews.nodes,
        blockingWarningCount: blockingProjections.counts.active,
        websocketReconnects: stats.websocketReconnects,
        websocketFailures: stats.websocketFailures,
        envelopesDropped: stats.envelopesDropped,
      }),
    [
      header.health,
      header.connection,
      header.warnings,
      header.taskCounts,
      header.eventRate,
      queueBundle.views,
      semaphoreBundle.views,
      executorBundle.views,
      dependencyViews.nodes,
      blockingProjections.counts.active,
      stats.websocketReconnects,
      stats.websocketFailures,
      stats.envelopesDropped,
    ],
  );

  const recommendations = useMemo(
    () =>
      deriveRuntimeRecommendations({
        queues: queueBundle.views,
        semaphores: semaphoreBundle.views,
        executors: executorBundle.views,
        dependencyNodes: dependencyViews.nodes,
        blockingWarningCount: blockingProjections.counts.active,
      }),
    [
      queueBundle.views,
      semaphoreBundle.views,
      executorBundle.views,
      dependencyViews.nodes,
      blockingProjections.counts.active,
    ],
  );

  const topSeverity = findings[0]?.severity ?? "info";

  return (
    <div className="flex h-full flex-col gap-6 overflow-auto p-6 text-sm text-text">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-mono text-base uppercase tracking-widest text-text">Diagnostics</h1>
          <OverallStatusPill severity={topSeverity} findings={findings} />
        </div>
        <Badge intent="accent">build {config.buildVersion}</Badge>
      </header>

      <Section
        title="Runtime Diagnostics"
        subtitle="Live signals projected from the runtime — what's wrong and how to fix it."
      >
        <div className="grid gap-3 lg:grid-cols-2">
          {findings.map((f) => (
            <FindingCard key={f.id} finding={f} />
          ))}
        </div>
      </Section>

      <Section
        title="Recommendations"
        subtitle="Short, imperative actions derived from the same signals."
      >
        {recommendations.length === 0 ? (
          <p className="font-mono text-xs text-subtle">
            No actionable recommendations — the runtime is operating inside expected envelopes.
          </p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {recommendations.map((r) => (
              <RecommendationCard key={r.id} recommendation={r} />
            ))}
          </div>
        )}
      </Section>

      <Section title="Runtime Summary" subtitle="At-a-glance counts across each subsystem.">
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <SummaryCount
            label="Tasks"
            value={header.taskCounts.total}
            sublabel={`${header.taskCounts.active} active · ${header.taskCounts.failed} failed`}
            intent={header.taskCounts.failed > 0 ? "warning" : "default"}
            href="/timeline"
          />
          <SummaryCount
            label="Queues"
            value={queueBundle.views.length}
            sublabel={`${queueBundle.alarmCount} alarmed`}
            intent={queueBundle.alarmCount > 0 ? "warning" : "default"}
            href="/queues"
          />
          <SummaryCount
            label="Semaphores"
            value={semaphoreBundle.views.length}
            sublabel={`${semaphoreBundle.alarmCount} alarmed`}
            intent={semaphoreBundle.alarmCount > 0 ? "warning" : "default"}
            href="/semaphores"
          />
          <SummaryCount
            label="Executors"
            value={executorBundle.views.length}
            sublabel={`${executorBundle.alarmCount} alarmed`}
            intent={executorBundle.alarmCount > 0 ? "warning" : "default"}
            href="/executors"
          />
          <SummaryCount
            label="Dependencies"
            value={dependencyViews.nodes.length}
            sublabel={`${dependencyViews.alarmCount} alarmed`}
            intent={dependencyViews.alarmCount > 0 ? "warning" : "default"}
            href="/dependencies"
          />
          <SummaryCount
            label="Replay"
            value={header.replay.lastSequence}
            sublabel={header.replay.isReplaying ? "Replaying" : "Idle"}
            intent={header.replay.isReplaying ? "accent" : "default"}
            href="/replay"
          />
          <SummaryCount
            label="Warnings"
            value={header.warnings.total}
            sublabel={
              header.warnings.highest ? `Highest: ${header.warnings.highest}` : "None active"
            }
            intent={
              header.warnings.highest === "critical" || header.warnings.highest === "error"
                ? "danger"
                : header.warnings.highest === "warning"
                  ? "warning"
                  : "default"
            }
            href="/warnings"
          />
          <SummaryCount
            label="Health"
            value={header.health.label}
            sublabel={header.connection.label}
            intent={healthIntent(header.health.level)}
          />
        </div>
      </Section>

      <Section
        title="Developer Diagnostics"
        subtitle="Frontend pipeline counters — collapsed by default. Open these when debugging the dashboard itself."
        collapsible
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          <Card>
            <h3 className="font-mono text-xs uppercase tracking-widest text-subtle">Config</h3>
            <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
              <dt className="text-muted">API base</dt>
              <dd className="text-text">{config.apiBaseUrl || "<same-origin>"}</dd>
              <dt className="text-muted">WS url</dt>
              <dd className="text-text">{config.websocketUrl}</dd>
              <dt className="text-muted">Protocol</dt>
              <dd className="text-text">{config.protocolVersion}</dd>
            </dl>
          </Card>

          <Card>
            <h3 className="font-mono text-xs uppercase tracking-widest text-subtle">Websocket</h3>
            <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
              <dt className="text-muted">attempts</dt>
              <dd className="text-text">{stats.websocketConnectAttempts}</dd>
              <dt className="text-muted">reconnects</dt>
              <dd className="text-text">{stats.websocketReconnects}</dd>
              <dt className="text-muted">failures</dt>
              <dd className="text-text">{stats.websocketFailures}</dd>
            </dl>
          </Card>

          <Card>
            <h3 className="font-mono text-xs uppercase tracking-widest text-subtle">Envelopes</h3>
            <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
              <dt className="text-muted">received</dt>
              <dd className="text-text">{stats.envelopesReceived}</dd>
              <dt className="text-muted">dropped</dt>
              <dd className="text-text">{stats.envelopesDropped}</dd>
              <dt className="text-muted">protocol mismatch</dt>
              <dd className="text-text">{stats.protocolMismatches}</dd>
            </dl>
          </Card>

          <Card>
            <h3 className="font-mono text-xs uppercase tracking-widest text-subtle">Hydration</h3>
            <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
              <dt className="text-muted">hydrations</dt>
              <dd className="text-text">{stats.snapshotHydrations}</dd>
              <dt className="text-muted">failures</dt>
              <dd className="text-text">{stats.snapshotHydrationFailures}</dd>
              <dt className="text-muted">render errors</dt>
              <dd className="text-text">{stats.renderErrors}</dd>
            </dl>
          </Card>

          <Card>
            <TaskDiagnostics />
          </Card>
          <Card>
            <MetricsDiagnostics />
          </Card>
          <Card>
            <RuntimeEventDiagnostics />
          </Card>
          <Card>
            <ConnectionDiagnostics />
          </Card>
          <Card>
            <TimelineDiagnostics />
          </Card>
          <Card>
            <BlockingWarningsDiagnostics />
          </Card>
          <Card>
            <FreezeRegionDiagnostics />
          </Card>
          <Card>
            <QueuePressureDiagnostics />
          </Card>
          <Card>
            <SemaphoreContentionDiagnostics />
          </Card>
          <Card>
            <AwaitDependencyDiagnostics />
          </Card>
          <Card>
            <ExecutorActivityDiagnostics />
          </Card>
        </div>
      </Section>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Finding + recommendation cards
// ──────────────────────────────────────────────────────────────────────────

function FindingCard({ finding }: { finding: RuntimeFinding }): JSX.Element {
  return (
    <Card padding="md" intent={severityIntent(finding.severity)} className="flex flex-col gap-2">
      <header className="flex items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <Badge intent={severityIntent(finding.severity)}>{finding.severity}</Badge>
          <h3 className="font-mono text-sm text-text">{finding.title}</h3>
        </div>
        <a
          href={`#${finding.jumpTarget}`}
          className="rounded border border-accent bg-accent/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-accent hover:bg-accent/15"
        >
          {finding.jumpLabel}
        </a>
      </header>
      <p className="font-mono text-xs text-muted">{finding.description}</p>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
        <dt className="text-[10px] uppercase tracking-widest text-muted">Impact</dt>
        <dd className="text-text">{finding.impact}</dd>
        <dt className="text-[10px] uppercase tracking-widest text-muted">Try</dt>
        <dd className="text-text">{finding.suggestedFix}</dd>
      </dl>
      {finding.relatedObjects.length > 0 && <RelatedRow related={finding.relatedObjects} />}
    </Card>
  );
}

function RelatedRow({ related }: { related: readonly RelatedRuntimeObject[] }): JSX.Element {
  return (
    <div className="flex flex-wrap items-baseline gap-2 border-t border-line/40 pt-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Related</span>
      {related.map((r) => (
        <span
          key={`${r.kind}-${r.id}`}
          className="rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-subtle"
          title={`${r.kind}: ${r.id}`}
        >
          {r.kind}: {r.label}
        </span>
      ))}
    </div>
  );
}

function RecommendationCard({
  recommendation,
}: {
  recommendation: RuntimeRecommendation;
}): JSX.Element {
  return (
    <Card padding="md" className="flex flex-col gap-2">
      <header className="flex items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <Badge intent={severityIntent(recommendation.severity)}>{recommendation.severity}</Badge>
          <h3 className="font-mono text-sm text-text">{recommendation.title}</h3>
        </div>
        <a
          href={`#${recommendation.jumpTarget}`}
          className="rounded border border-line bg-canvas px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
        >
          {recommendation.jumpLabel}
        </a>
      </header>
      <p className="font-mono text-xs text-muted">{recommendation.rationale}</p>
    </Card>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Summary cells
// ──────────────────────────────────────────────────────────────────────────

function SummaryCount({
  label,
  value,
  sublabel,
  intent = "default",
  href,
}: {
  label: string;
  value: number | string;
  sublabel: string;
  intent?: Intent;
  href?: string;
}): JSX.Element {
  const content = (
    <Card padding="sm" intent={intent} className="flex flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className="truncate font-mono text-lg tabular-nums text-text">
        {typeof value === "number" ? value.toLocaleString() : value}
      </span>
      <span className="truncate font-mono text-[10px] uppercase tracking-widest text-subtle">
        {sublabel}
      </span>
    </Card>
  );
  if (href === undefined) return content;
  return (
    <a href={`#${href}`} className="contents">
      {content}
    </a>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Section shell (with optional collapse)
// ──────────────────────────────────────────────────────────────────────────

function Section({
  title,
  subtitle,
  children,
  collapsible,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  collapsible?: boolean;
}): JSX.Element {
  const [open, setOpen] = useState(!collapsible);
  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-baseline justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <h2 className="font-mono text-xs uppercase tracking-widest text-text">{title}</h2>
          {subtitle !== undefined && <p className="font-mono text-[11px] text-muted">{subtitle}</p>}
        </div>
        {collapsible === true && (
          <button
            type="button"
            onClick={() => setOpen((prev) => !prev)}
            aria-expanded={open}
            className="rounded border border-line bg-canvas px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
          >
            {open ? "Collapse" : "Expand"}
          </button>
        )}
      </header>
      {open && children}
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Overall status pill (header)
// ──────────────────────────────────────────────────────────────────────────

function OverallStatusPill({
  severity,
  findings,
}: {
  severity: FindingSeverity;
  findings: readonly RuntimeFinding[];
}): JSX.Element {
  const critical = findings.filter((f) => f.severity === "critical").length;
  const warning = findings.filter((f) => f.severity === "warning").length;
  let label: string;
  let intent: Intent;
  if (critical > 0) {
    label = `${critical} critical · ${warning} warning${warning === 1 ? "" : "s"}`;
    intent = "danger";
  } else if (warning > 0) {
    label = `${warning} warning${warning === 1 ? "" : "s"}`;
    intent = "warning";
  } else if (severity === "info" && findings[0]?.id === "healthy") {
    label = "Healthy";
    intent = "success";
  } else {
    label = "Active";
    intent = "accent";
  }
  return <Badge intent={intent}>{label}</Badge>;
}

// ──────────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────────

function severityIntent(severity: FindingSeverity): Intent {
  switch (severity) {
    case "critical":
      return "danger";
    case "warning":
      return "warning";
    case "info":
    default:
      return "accent";
  }
}

function healthIntent(level: string): Intent {
  switch (level) {
    case "healthy":
      return "success";
    case "degraded":
      return "warning";
    case "unavailable":
      return "danger";
    default:
      return "default";
  }
}

function projectStats(
  snap: ReturnType<ReturnType<typeof useClientMetrics>["snapshot"]>,
): ClientStats {
  return {
    envelopesReceived: snap.envelopesReceived,
    envelopesDropped: snap.envelopesDropped,
    websocketConnectAttempts: snap.websocketConnectAttempts,
    websocketReconnects: snap.websocketReconnects,
    websocketFailures: snap.websocketFailures,
    protocolMismatches: snap.protocolMismatches,
    snapshotHydrations: snap.snapshotHydrations,
    snapshotHydrationFailures: snap.snapshotHydrationFailures,
    renderErrors: snap.renderErrors,
  };
}
