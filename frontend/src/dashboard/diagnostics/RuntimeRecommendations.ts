/**
 * Runtime recommendations.
 *
 * The findings module says *what is wrong*. This module turns the
 * same signals into short *actions the operator can take*. They're
 * intentionally one-line + imperative so the recommendation card can
 * be skimmed in a glance.
 *
 * Recommendations are only emitted when their triggering condition
 * is present; the panel hides when the array is empty rather than
 * inventing busywork.
 */

import type { QueuePressureView } from "@/dashboard/queues/models/QueuePressureModels";
import type { SemaphoreContentionView } from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import type { ExecutorActivityView } from "@/dashboard/executors/models/ExecutorActivityModels";
import type { AwaitNodeView } from "@/dashboard/dependencies/models/AwaitDependencyModels";

export interface RuntimeRecommendation {
  readonly id: string;
  /** Imperative one-liner shown as the card title. */
  readonly title: string;
  /** A sentence of context — why this is worth doing. */
  readonly rationale: string;
  /** Severity drives the chip color. */
  readonly severity: "info" | "warning" | "critical";
  /** Page route the operator should open to act on this. */
  readonly jumpTarget: string;
  readonly jumpLabel: string;
}

export interface RuntimeRecommendationInputs {
  readonly queues: readonly QueuePressureView[];
  readonly semaphores: readonly SemaphoreContentionView[];
  readonly executors: readonly ExecutorActivityView[];
  readonly dependencyNodes: readonly AwaitNodeView[];
  readonly blockingWarningCount: number;
}

export function deriveRuntimeRecommendations(
  inputs: RuntimeRecommendationInputs,
): readonly RuntimeRecommendation[] {
  const out: RuntimeRecommendation[] = [];

  // ── executor advice ────────────────────────────────────────────────
  const executorOverflow = inputs.executors.filter(
    (e) =>
      e.maxWorkers !== null
      && e.activeWorkers >= e.maxWorkers
      && (e.severity === "saturated" || e.severity === "critical"),
  );
  if (executorOverflow.length > 0) {
    out.push({
      id: "rec-increase-executor-workers",
      title: "Increase executor workers",
      rationale: `${executorOverflow.length} executor${executorOverflow.length === 1 ? "" : "s"} are at max_workers with backlog growing. Raising max_workers (or moving to a process pool) absorbs the burst.`,
      severity: "critical",
      jumpTarget: "/executors",
      jumpLabel: "Open Executors",
    });
  }

  const executorBacklog = inputs.executors.filter((e) => e.backlog > 0);
  if (executorBacklog.length > 0) {
    out.push({
      id: "rec-batch-writes",
      title: "Batch writes into the executor",
      rationale: `Executor backlog is non-zero on ${executorBacklog.length} pool${executorBacklog.length === 1 ? "" : "s"}. Combining many small submissions into one larger one cuts per-task overhead.`,
      severity: executorBacklog.length >= 2 ? "warning" : "info",
      jumpTarget: "/executors",
      jumpLabel: "Open Executors",
    });
  }

  // ── queue advice ───────────────────────────────────────────────────
  const queuePressure = inputs.queues.filter(
    (q) => q.severity === "saturated" || q.severity === "critical",
  );
  if (queuePressure.length > 0) {
    const skewedProducers = queuePressure.filter(
      (q) => q.producerConsumerDelta > 0,
    );
    if (skewedProducers.length > 0) {
      out.push({
        id: "rec-reduce-producer-throughput",
        title: "Reduce producer throughput",
        rationale: `Producers are outpacing consumers on ${skewedProducers.length} queue${skewedProducers.length === 1 ? "" : "s"}. Backpressure or rate-limit the producer side to drain the backlog.`,
        severity: "warning",
        jumpTarget: "/queues",
        jumpLabel: "Open Queues",
      });
    }
    const fullishQueues = queuePressure.filter(
      (q) => q.maxsize > 0 && q.currentSize / q.maxsize >= 0.9,
    );
    if (fullishQueues.length > 0) {
      out.push({
        id: "rec-increase-queue-capacity",
        title: "Increase queue capacity",
        rationale: `${fullishQueues.length} bounded queue${fullishQueues.length === 1 ? "" : "s"} are ≥ 90% full. If the burst is bounded, a larger 'maxsize' smooths it without changing throughput.`,
        severity: "warning",
        jumpTarget: "/queues",
        jumpLabel: "Open Queues",
      });
    }
  }

  // ── semaphore advice ───────────────────────────────────────────────
  const semaphoreSaturated = inputs.semaphores.filter(
    (s) => s.severity === "saturated" || s.severity === "critical",
  );
  if (semaphoreSaturated.length > 0) {
    out.push({
      id: "rec-bounded-semaphore",
      title: "Convert to a bounded acquire-or-skip",
      rationale: `${semaphoreSaturated.length} semaphore${semaphoreSaturated.length === 1 ? "" : "s"} have permanent waiters. If the work is shed-able, 'acquire(timeout=...)' + a fallback avoids unbounded queueing.`,
      severity: "warning",
      jumpTarget: "/semaphores",
      jumpLabel: "Open Semaphores",
    });
  }

  // ── gather / dependency advice ─────────────────────────────────────
  const gatherTrouble = inputs.dependencyNodes.filter(
    (n) =>
      n.kind === "gather"
      && (n.state === "failed" || n.state === "cancelled"),
  );
  if (gatherTrouble.length > 0) {
    out.push({
      id: "rec-avoid-nested-gather",
      title: "Avoid nested gather",
      rationale: `${gatherTrouble.length} gather call${gatherTrouble.length === 1 ? "" : "s"} ended in failure or cancellation. Nesting gathers hides the propagation order — flatten them or pass 'return_exceptions=True'.`,
      severity: "warning",
      jumpTarget: "/dependencies",
      jumpLabel: "Open Dependencies",
    });
  }

  // ── blocking advice ────────────────────────────────────────────────
  if (inputs.blockingWarningCount > 0) {
    out.push({
      id: "rec-replace-blocking-call",
      title: "Replace blocking calls with asyncio.to_thread",
      rationale: `${inputs.blockingWarningCount} blocking-call warning${inputs.blockingWarningCount === 1 ? "" : "s"} active. Moving the call into a thread frees the event loop for every other coroutine.`,
      severity: inputs.blockingWarningCount >= 3 ? "critical" : "warning",
      jumpTarget: "/warnings",
      jumpLabel: "Open Warnings",
    });
    if (inputs.blockingWarningCount >= 2) {
      out.push({
        id: "rec-split-long-coroutine",
        title: "Split long-running coroutines",
        rationale: "Multiple blocking warnings suggest a single coroutine is doing too much synchronous work. Breaking it into smaller `await` points lets the loop schedule other tasks.",
        severity: "warning",
        jumpTarget: "/warnings",
        jumpLabel: "Open Warnings",
      });
    }
  }

  // Sort criticals first.
  out.sort((a, b) => rank(b.severity) - rank(a.severity));
  return out;
}

function rank(s: RuntimeRecommendation["severity"]): number {
  return s === "critical" ? 3 : s === "warning" ? 2 : 1;
}
