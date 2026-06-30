/**
 * Runtime findings derivation.
 *
 * Folds the existing projection bundles (queues / semaphores /
 * executors / dependencies / blocking warnings / connection summary)
 * into a list of *findings* — short, human-readable diagnoses that
 * tell the operator **what is wrong**, **why it matters**, and
 * **what to try next**, rather than dumping more counters.
 *
 * Pure module — every input is plain data, the output is a stable
 * array. The component consumes it through ``useRuntimeFindings``
 * which wires the right hooks. Easy to unit-test in isolation.
 */

import type {
  ConnectionSummary,
  RuntimeHealthSummary,
  WarningSummary,
  TaskCountSummary,
  EventRateSummary,
} from "@/dashboard/metrics/models/summary";
import type { QueuePressureView } from "@/dashboard/queues/models/QueuePressureModels";
import type { SemaphoreContentionView } from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import type { ExecutorActivityView } from "@/dashboard/executors/models/ExecutorActivityModels";
import type { AwaitNodeView } from "@/dashboard/dependencies/models/AwaitDependencyModels";

/** Finding severity — mirrors the warning store's severity but
 *  collapses ``error`` and ``critical`` into one ``critical`` bucket
 *  for surface simplicity. */
export type FindingSeverity = "info" | "warning" | "critical";

export interface RelatedRuntimeObject {
  readonly kind: "queue" | "semaphore" | "executor" | "dependency" | "task" | "warning" | "connection" | "replay";
  readonly id: string;
  readonly label: string;
}

export interface RuntimeFinding {
  /** Stable id — used as React key + scroll target. */
  readonly id: string;
  readonly title: string;
  readonly severity: FindingSeverity;
  /** What the dashboard sees. */
  readonly description: string;
  /** Why the operator should care. */
  readonly impact: string;
  /** What to try. */
  readonly suggestedFix: string;
  /** Subsystem objects involved — for the "Related" badges row. */
  readonly relatedObjects: readonly RelatedRuntimeObject[];
  /** Sidebar/page route to open when the user clicks "Jump". */
  readonly jumpTarget: string;
  /** Label for the Jump button (e.g. "Open Queues"). */
  readonly jumpLabel: string;
}

export interface RuntimeFindingsInputs {
  readonly health: RuntimeHealthSummary;
  readonly connection: ConnectionSummary;
  readonly warnings: WarningSummary;
  readonly tasks: TaskCountSummary;
  readonly eventRate: EventRateSummary;
  readonly queues: readonly QueuePressureView[];
  readonly semaphores: readonly SemaphoreContentionView[];
  readonly executors: readonly ExecutorActivityView[];
  readonly dependencyNodes: readonly AwaitNodeView[];
  readonly blockingWarningCount: number;
  /** Lifetime websocket counters from the client metrics snapshot. */
  readonly websocketReconnects: number;
  readonly websocketFailures: number;
  readonly envelopesDropped: number;
}

/** Cap on related-object badges per finding — keeps the card legible
 *  on dashboards with dozens of saturated objects. */
const RELATED_CAP = 4;

export function deriveRuntimeFindings(
  inputs: RuntimeFindingsInputs,
): readonly RuntimeFinding[] {
  const out: RuntimeFinding[] = [];

  out.push(...queueFindings(inputs.queues));
  out.push(...semaphoreFindings(inputs.semaphores));
  out.push(...executorFindings(inputs.executors));
  out.push(...dependencyFindings(inputs.dependencyNodes));
  out.push(...blockingFindings(inputs.blockingWarningCount));
  out.push(...taskFailureFindings(inputs.tasks));
  out.push(...connectionFindings(inputs.connection, inputs.websocketReconnects, inputs.websocketFailures));
  out.push(...eventRateFindings(inputs.eventRate, inputs.envelopesDropped));
  out.push(...healthFindings(inputs.health, inputs.warnings));

  // Sort criticals first, then warnings, then info; preserve
  // discovery order otherwise.
  out.sort((a, b) => severityRank(b.severity) - severityRank(a.severity));

  if (out.length === 0) {
    out.push(healthyFinding());
  }
  return out;
}

// ── per-subsystem rules ──────────────────────────────────────────────────

function queueFindings(
  queues: readonly QueuePressureView[],
): RuntimeFinding[] {
  const saturated = queues.filter((q) => q.severity === "saturated");
  const critical = queues.filter((q) => q.severity === "critical");
  const warning = queues.filter((q) => q.severity === "warning");

  const findings: RuntimeFinding[] = [];

  if (saturated.length > 0) {
    findings.push({
      id: "queue-saturation",
      title: "Queue saturation",
      severity: "critical",
      description: describeQueueGroup(saturated, "is saturated"),
      impact:
        "Producers are blocking on .put(); throughput is capped at consumer speed and latency for upstream callers climbs.",
      suggestedFix:
        "Increase queue capacity, throttle producers, or add consumers. If saturation is bursty, consider a bounded executor pool to absorb spikes.",
      relatedObjects: queueRelated(saturated),
      jumpTarget: "/queues",
      jumpLabel: "Open Queues",
    });
  } else if (critical.length > 0) {
    findings.push({
      id: "queue-critical-pressure",
      title: "Queue under critical pressure",
      severity: "critical",
      description: describeQueueGroup(critical, "is under critical pressure"),
      impact:
        "Backlog is growing faster than it drains. The queue will saturate soon if the trend continues.",
      suggestedFix:
        "Reduce producer throughput, scale up consumers, or batch writes into the queue.",
      relatedObjects: queueRelated(critical),
      jumpTarget: "/queues",
      jumpLabel: "Open Queues",
    });
  } else if (warning.length > 0) {
    findings.push({
      id: "queue-warning-pressure",
      title: "Queue showing pressure",
      severity: "warning",
      description: describeQueueGroup(warning, "is showing pressure"),
      impact:
        "Producers occasionally block. Latency may rise during burst windows.",
      suggestedFix:
        "Check consumer throughput; if it's CPU-bound, move heavy work into an executor.",
      relatedObjects: queueRelated(warning),
      jumpTarget: "/queues",
      jumpLabel: "Open Queues",
    });
  }
  return findings;
}

function semaphoreFindings(
  semaphores: readonly SemaphoreContentionView[],
): RuntimeFinding[] {
  const blocked = semaphores.filter(
    (s) => s.severity === "saturated" || s.severity === "critical",
  );
  const contended = semaphores.filter((s) => s.severity === "warning");
  const findings: RuntimeFinding[] = [];
  if (blocked.length > 0) {
    findings.push({
      id: "semaphore-contention",
      title: "Semaphore contention",
      severity: "critical",
      description: describeSemaphoreGroup(blocked),
      impact:
        "Coroutines pile up behind the semaphore; downstream tasks miss deadlines and timeouts may cascade.",
      suggestedFix:
        "Raise the permit count if the protected resource can handle more concurrency, or convert to a bounded acquire-or-skip pattern.",
      relatedObjects: semaphoreRelated(blocked),
      jumpTarget: "/semaphores",
      jumpLabel: "Open Semaphores",
    });
  } else if (contended.length > 0) {
    findings.push({
      id: "semaphore-warning",
      title: "Semaphore showing contention",
      severity: "warning",
      description: describeSemaphoreGroup(contended),
      impact:
        "Waiters are accumulating intermittently; throughput is partly gated on this semaphore.",
      suggestedFix:
        "Audit the critical section it protects — shrinking it (or batching acquisitions) often resolves contention without touching the permit count.",
      relatedObjects: semaphoreRelated(contended),
      jumpTarget: "/semaphores",
      jumpLabel: "Open Semaphores",
    });
  }
  return findings;
}

function executorFindings(
  executors: readonly ExecutorActivityView[],
): RuntimeFinding[] {
  const saturated = executors.filter(
    (e) => e.severity === "saturated" || e.severity === "critical",
  );
  const warning = executors.filter((e) => e.severity === "warning");
  const findings: RuntimeFinding[] = [];
  if (saturated.length > 0) {
    findings.push({
      id: "executor-saturation",
      title: "Executor saturation",
      severity: "critical",
      description: describeExecutorGroup(saturated),
      impact:
        "All workers are busy and the backlog is growing. Submitted callables stall in the queue; latency on every executor call rises.",
      suggestedFix:
        "Increase ``max_workers`` if the host has headroom, or move CPU-bound work onto a dedicated process pool. Long callables should be split.",
      relatedObjects: executorRelated(saturated),
      jumpTarget: "/executors",
      jumpLabel: "Open Executors",
    });
  } else if (warning.length > 0) {
    findings.push({
      id: "executor-warning",
      title: "Executor under pressure",
      severity: "warning",
      description: describeExecutorGroup(warning),
      impact:
        "The executor is approaching its worker cap; small bursts push it into saturation.",
      suggestedFix:
        "Profile callables for unexpectedly long work; consider batching writes or splitting long-running callables.",
      relatedObjects: executorRelated(warning),
      jumpTarget: "/executors",
      jumpLabel: "Open Executors",
    });
  }
  return findings;
}

function dependencyFindings(
  nodes: readonly AwaitNodeView[],
): RuntimeFinding[] {
  const failed = nodes.filter(
    (n) => n.kind === "gather" && n.state === "failed",
  );
  const cancelled = nodes.filter(
    (n) => n.kind === "gather" && n.state === "cancelled",
  );
  const stuckGathers = nodes.filter(
    (n) =>
      n.kind === "gather"
      && n.state === "pending"
      && n.childCount > 0
      && n.completedCount + n.failedCount + n.cancelledCount === 0,
  );

  const findings: RuntimeFinding[] = [];
  if (failed.length > 0) {
    findings.push({
      id: "gather-failures",
      title: "Gather failures",
      severity: "critical",
      description: `${failed.length} gather call${failed.length === 1 ? "" : "s"} resolved with a failure — the parent task surface the first exception while peers are cancelled.`,
      impact:
        "Failed gathers tend to leak partial work: cancelled siblings may have committed half their changes before the cancel landed.",
      suggestedFix:
        "Use ``return_exceptions=True`` to inspect each child, or wrap each branch in its own try/except so cleanup runs before the outer gather raises.",
      relatedObjects: failed.slice(0, RELATED_CAP).map((n) => ({
        kind: "dependency" as const,
        id: n.id,
        label: n.label ?? n.id,
      })),
      jumpTarget: "/dependencies",
      jumpLabel: "Open Dependencies",
    });
  }
  if (cancelled.length > 0) {
    findings.push({
      id: "gather-cancellations",
      title: "Gather cancellations",
      severity: "warning",
      description: `${cancelled.length} gather call${cancelled.length === 1 ? "" : "s"} were cancelled mid-flight.`,
      impact:
        "Cancellation cascades through siblings — half-finished I/O may leave external state inconsistent.",
      suggestedFix:
        "Audit the cancellation source. If the cancel is intentional, add cleanup blocks. If not, the parent's deadline / scope is likely too tight.",
      relatedObjects: cancelled.slice(0, RELATED_CAP).map((n) => ({
        kind: "dependency" as const,
        id: n.id,
        label: n.label ?? n.id,
      })),
      jumpTarget: "/dependencies",
      jumpLabel: "Open Dependencies",
    });
  }
  if (stuckGathers.length > 0) {
    findings.push({
      id: "gather-deadlock-suspect",
      title: "Possible deadlock",
      severity: "critical",
      description: `${stuckGathers.length} gather call${stuckGathers.length === 1 ? "" : "s"} have made no progress — every child is still pending.`,
      impact:
        "If children are awaiting each other or an external signal that won't fire, the calling task is stuck forever.",
      suggestedFix:
        "Inspect the children's awaits; look for cyclic await chains or unbounded waits on events that no one sets.",
      relatedObjects: stuckGathers.slice(0, RELATED_CAP).map((n) => ({
        kind: "dependency" as const,
        id: n.id,
        label: n.label ?? n.id,
      })),
      jumpTarget: "/dependencies",
      jumpLabel: "Open Dependencies",
    });
  }
  return findings;
}

function blockingFindings(blockingWarningCount: number): RuntimeFinding[] {
  if (blockingWarningCount <= 0) return [];
  const severity: FindingSeverity =
    blockingWarningCount >= 3 ? "critical" : "warning";
  return [
    {
      id: "blocking-callbacks",
      title: "Blocking call inside the event loop",
      severity,
      description: `${blockingWarningCount} active blocking-call warning${blockingWarningCount === 1 ? "" : "s"}. A coroutine called into synchronous I/O or CPU-bound code without yielding.`,
      impact:
        "Every other task on the loop is paused while the blocking call runs. Tail latency rises; heartbeats and timers slip.",
      suggestedFix:
        "Move the blocking call into ``asyncio.to_thread()`` or a process pool. If the call is CPU-heavy, split the loop body so it yields control regularly.",
      relatedObjects: [],
      jumpTarget: "/warnings",
      jumpLabel: "Open Warnings",
    },
  ];
}

function taskFailureFindings(tasks: TaskCountSummary): RuntimeFinding[] {
  if (tasks.failed <= 0) return [];
  const severity: FindingSeverity = tasks.failed >= 5 ? "critical" : "warning";
  return [
    {
      id: "task-failures",
      title: "Task failures",
      severity,
      description: `${tasks.failed} task${tasks.failed === 1 ? "" : "s"} failed since session start (out of ${tasks.total} observed).`,
      impact:
        "Unhandled exceptions reduce throughput and can leave shared state in an inconsistent intermediate state.",
      suggestedFix:
        "Open the timeline for the failed tasks; the inspector shows the exception type + stack. Add an exception handler at the right scope.",
      relatedObjects: [],
      jumpTarget: "/timeline",
      jumpLabel: "Open Timeline",
    },
  ];
}

function connectionFindings(
  connection: ConnectionSummary,
  websocketReconnects: number,
  websocketFailures: number,
): RuntimeFinding[] {
  const findings: RuntimeFinding[] = [];
  // "Reconnect storm" — more than 2 reconnects since the session
  // started OR an active reconnect loop.
  if (websocketReconnects >= 3 || (connection.isReconnecting && connection.reconnectAttempts >= 2)) {
    findings.push({
      id: "reconnect-storm",
      title: "Reconnect storm",
      severity: "warning",
      description: `${websocketReconnects} websocket reconnect${websocketReconnects === 1 ? "" : "s"} this session${connection.isReconnecting ? "; currently reconnecting" : ""}.`,
      impact:
        "Each reconnect re-hydrates the snapshot. Charts flash and the dashboard briefly shows stale state.",
      suggestedFix:
        "Check network health and proxy timeouts. If the server is healthy, look for client-side load (browser tab CPU starvation).",
      relatedObjects: [
        { kind: "connection", id: "websocket", label: connection.label },
      ],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  if (websocketFailures > 0) {
    findings.push({
      id: "websocket-failures",
      title: "Websocket failures",
      severity: "warning",
      description: `${websocketFailures} websocket failure${websocketFailures === 1 ? "" : "s"} since the dashboard started.`,
      impact:
        "Failures mean the dashboard temporarily lost the live stream and reverted to its last hydrated snapshot.",
      suggestedFix:
        "Inspect the developer diagnostics for the failure cause (timeout vs handshake error vs server kicked).",
      relatedObjects: [
        { kind: "connection", id: "websocket", label: connection.label },
      ],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  if (connection.hasError && !connection.isLive) {
    findings.push({
      id: "connection-error",
      title: "Live connection lost",
      severity: "critical",
      description: `Websocket is in '${connection.label}' state — no live data flowing.`,
      impact:
        "Every metric on the dashboard is frozen at the moment the connection dropped.",
      suggestedFix:
        "Check that ``asyncviz run`` (or your dashboard host) is still running. The frontend will reconnect automatically once it's reachable.",
      relatedObjects: [
        { kind: "connection", id: "websocket", label: connection.label },
      ],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  return findings;
}

function eventRateFindings(
  eventRate: EventRateSummary,
  envelopesDropped: number,
): RuntimeFinding[] {
  const findings: RuntimeFinding[] = [];
  if (eventRate.duplicatesDropped > 0) {
    findings.push({
      id: "duplicate-events",
      title: "Duplicate events suppressed",
      severity: "info",
      description: `${eventRate.duplicatesDropped} duplicate envelope${eventRate.duplicatesDropped === 1 ? "" : "s"} dropped — same sequence delivered more than once.`,
      impact:
        "Cosmetic. The store deduplicates correctly; this counter just indicates the upstream pipeline sent repeats.",
      suggestedFix:
        "If the count is growing fast, check whether multiple bridges are wired to the same source.",
      relatedObjects: [],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  if (eventRate.staleDropped > 0) {
    findings.push({
      id: "stale-events",
      title: "Stale events dropped",
      severity: "info",
      description: `${eventRate.staleDropped} stale-sequence envelope${eventRate.staleDropped === 1 ? "" : "s"} dropped — sequence went backwards.`,
      impact:
        "Indicates a reconnect or replay window switch. Harmless unless growing during steady state.",
      suggestedFix:
        "If it grows in steady state, the server clock is jumping or a replay buffer is being re-served.",
      relatedObjects: [],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  if (envelopesDropped > 0) {
    findings.push({
      id: "dropped-events",
      title: "Dropped events",
      severity: "warning",
      description: `${envelopesDropped} envelope${envelopesDropped === 1 ? "" : "s"} could not be applied to the store.`,
      impact:
        "Some on-screen metrics are slightly behind the runtime. The store catches up after the next snapshot.",
      suggestedFix:
        "If the count is large, check websocket flow control + browser tab throttling.",
      relatedObjects: [],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  if (eventRate.protocolErrors > 0) {
    findings.push({
      id: "protocol-errors",
      title: "Protocol errors",
      severity: "warning",
      description: `${eventRate.protocolErrors} envelope${eventRate.protocolErrors === 1 ? "" : "s"} rejected for protocol mismatch.`,
      impact:
        "Frontend ⇆ backend wire versions disagree. Some envelopes are being thrown away on arrival.",
      suggestedFix:
        "Rebuild + re-embed the frontend (``make embed-frontend``) so its protocol version matches the running backend.",
      relatedObjects: [],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  return findings;
}

function healthFindings(
  health: RuntimeHealthSummary,
  warnings: WarningSummary,
): RuntimeFinding[] {
  const findings: RuntimeFinding[] = [];
  if (health.level === "starting" || health.isHydrating) {
    findings.push({
      id: "runtime-starting",
      title: "Runtime starting up",
      severity: "info",
      description: "The dashboard is still hydrating its initial snapshot from the backend.",
      impact:
        "Metrics may briefly show empty or zero values until hydration completes.",
      suggestedFix:
        "Wait a few seconds — the runtime will transition to 'healthy' once the first snapshot has been applied.",
      relatedObjects: [],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  if (health.level === "unavailable") {
    findings.push({
      id: "runtime-unavailable",
      title: "Runtime unavailable",
      severity: "critical",
      description: "The backend is not responding to health probes.",
      impact:
        "No live data is reaching the dashboard. Every panel is frozen at its last hydrated value.",
      suggestedFix:
        "Verify the ``asyncviz`` process is running and reachable on the configured port.",
      relatedObjects: [],
      jumpTarget: "/diagnostics",
      jumpLabel: "Developer diagnostics",
    });
  }
  if (warnings.highest === "critical" && warnings.total > 0) {
    findings.push({
      id: "active-critical-warnings",
      title: "Active critical warnings",
      severity: "critical",
      description: `${warnings.total} active runtime warning${warnings.total === 1 ? "" : "s"}, ${warnings.countsBySeverity.critical} at critical severity.`,
      impact:
        "Critical warnings indicate runtime invariants the backend believes have been violated.",
      suggestedFix:
        "Open the warnings panel — each warning carries its source + stack frame to localize the cause.",
      relatedObjects: [],
      jumpTarget: "/warnings",
      jumpLabel: "Open Warnings",
    });
  }
  return findings;
}

function healthyFinding(): RuntimeFinding {
  return {
    id: "healthy",
    title: "Runtime is healthy",
    severity: "info",
    description:
      "No queue saturation, semaphore contention, executor pressure, blocking calls, or connection issues detected.",
    impact:
      "Every subsystem is operating inside its expected envelope.",
    suggestedFix:
      "Nothing to do. The runtime summary below shows current counts for reference.",
    relatedObjects: [],
    jumpTarget: "/timeline",
    jumpLabel: "Open Timeline",
  };
}

// ── describe helpers (kept short — these read inside the card) ──────────

function describeQueueGroup(
  views: readonly QueuePressureView[],
  trailing: string,
): string {
  const names = views.slice(0, 3).map((v) => v.displayName);
  const rest = views.length > 3 ? ` (+${views.length - 3} more)` : "";
  return `${names.join(", ")}${rest} ${trailing}.`;
}

function describeSemaphoreGroup(
  views: readonly SemaphoreContentionView[],
): string {
  const sample = views.slice(0, 3);
  const rest = views.length > 3 ? ` (+${views.length - 3} more)` : "";
  return sample
    .map((v) => `${v.displayName}: ${v.waiterCount} waiter(s), ${v.currentValue}/${v.initialValue} permits free`)
    .join("; ")
    .concat(rest, ".");
}

function describeExecutorGroup(
  views: readonly ExecutorActivityView[],
): string {
  const sample = views.slice(0, 3);
  const rest = views.length > 3 ? ` (+${views.length - 3} more)` : "";
  return sample
    .map(
      (v) =>
        `${v.displayName}: ${v.activeWorkers}/${v.maxWorkers} workers active, backlog ${v.backlog}`,
    )
    .join("; ")
    .concat(rest, ".");
}

function queueRelated(
  views: readonly QueuePressureView[],
): readonly RelatedRuntimeObject[] {
  return views.slice(0, RELATED_CAP).map((v) => ({
    kind: "queue" as const,
    id: v.queueId,
    label: v.displayName,
  }));
}

function semaphoreRelated(
  views: readonly SemaphoreContentionView[],
): readonly RelatedRuntimeObject[] {
  return views.slice(0, RELATED_CAP).map((v) => ({
    kind: "semaphore" as const,
    id: v.semaphoreId,
    label: v.displayName,
  }));
}

function executorRelated(
  views: readonly ExecutorActivityView[],
): readonly RelatedRuntimeObject[] {
  return views.slice(0, RELATED_CAP).map((v) => ({
    kind: "executor" as const,
    id: v.executorId,
    label: v.displayName,
  }));
}

function severityRank(severity: FindingSeverity): number {
  switch (severity) {
    case "critical":
      return 3;
    case "warning":
      return 2;
    case "info":
    default:
      return 1;
  }
}
