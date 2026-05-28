/**
 * Integration tests for :class:`MetricsHeader` + :class:`MetricsHeaderContainer`.
 *
 * Tests mount the canonical provider stack via :func:`renderWithProviders`
 * so the Zustand store + the rolling-rate hooks resolve. The store is
 * mutated directly between cases.
 */

import { describe, expect, it, beforeEach } from "vitest";
import { act } from "react";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { useRuntimeStore } from "@/state/runtime/store";
import { MetricsHeaderContainer } from "@/dashboard/metrics/components/MetricsHeaderContainer";
import { MetricsHeader } from "@/dashboard/metrics/components/MetricsHeader";
import { projectMetricsHeader } from "@/dashboard/metrics/selectors/projectSummaries";
import {
  resetMetricsHeaderMetrics,
  getMetricsHeaderMetrics,
} from "@/dashboard/metrics/observability";
import type { ProjectionInputs } from "@/dashboard/metrics/selectors/projectSummaries";
import { INITIAL_RECONCILIATION_STATS, INITIAL_RUNTIME_META } from "@/state/runtime/models";

function syntheticInputs(overrides: Partial<ProjectionInputs> = {}): ProjectionInputs {
  return {
    connection: { phase: "live", state: "open", reconnectAttempts: 0, lastFrameAtMonotonicMs: 0 },
    runtime: {
      ...INITIAL_RUNTIME_META,
      runtimeId: "rt-1",
      status: "running",
      connectedClients: 3,
    },
    replay: { oldestRetainedSequence: 0, newestRetainedSequence: 100, windowHit: true },
    timeline: {
      segmentsById: {},
      activeSegmentsByTaskId: {},
      segmentIdsByTaskId: {},
      lastSequence: 0,
    },
    warnings: {
      warningsById: {},
      activeWarningIds: [],
      resolvedWarningIds: [],
      countsBySeverity: { info: 0, warning: 0, error: 0, critical: 0 },
    },
    metrics: { aggregate: null, deltaCounts: {} },
    stats: {
      ...INITIAL_RECONCILIATION_STATS,
      envelopesApplied: 50,
      hydrations: 1,
    },
    tasksById: {},
    taskIdsByState: {
      created: [],
      running: [],
      waiting: [],
      completed: [],
      cancelled: [],
      failed: [],
    },
    lastSequence: 50,
    nowMs: 1000,
    envelopesPerSecond: 4,
    ...overrides,
  };
}

describe("MetricsHeader (presentational)", () => {
  it("renders the canonical region with every card", () => {
    const snapshot = projectMetricsHeader(syntheticInputs());
    renderWithProviders(<MetricsHeader snapshot={snapshot} />);
    const region = screen.getByRole("region", { name: /Runtime metrics/i });
    expect(region).toBeInTheDocument();
    // Every card has a stable data-metrics-card attribute we can probe.
    expect(region.querySelectorAll("[data-metrics-card]").length).toBe(8);
  });

  it("renders the runtime health label", () => {
    const snapshot = projectMetricsHeader(syntheticInputs());
    renderWithProviders(<MetricsHeader snapshot={snapshot} />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("renders the connection phase + reconnect detail", () => {
    const snapshot = projectMetricsHeader(
      syntheticInputs({
        connection: {
          phase: "reconnecting",
          state: "connecting",
          reconnectAttempts: 3,
          lastFrameAtMonotonicMs: 0,
        },
      }),
    );
    renderWithProviders(<MetricsHeader snapshot={snapshot} />);
    expect(screen.getByText(/Retry 3/i)).toBeInTheDocument();
  });

  it("renders the warning aggregation breakdown", () => {
    const snapshot = projectMetricsHeader(
      syntheticInputs({
        warnings: {
          warningsById: {},
          activeWarningIds: ["w1", "w2"],
          resolvedWarningIds: [],
          countsBySeverity: { info: 0, warning: 1, error: 1, critical: 0 },
        },
      }),
    );
    renderWithProviders(<MetricsHeader snapshot={snapshot} />);
    expect(screen.getByText(/C 0 · E 1 · W 1 · I 0/)).toBeInTheDocument();
  });

  it("renders the replay window state", () => {
    const snapshot = projectMetricsHeader(
      syntheticInputs({
        replay: { windowHit: false, oldestRetainedSequence: null, newestRetainedSequence: null },
      }),
    );
    renderWithProviders(<MetricsHeader snapshot={snapshot} />);
    expect(screen.getByText(/Cold restart/i)).toBeInTheDocument();
  });
});

describe("MetricsHeaderContainer", () => {
  beforeEach(() => {
    resetMetricsHeaderMetrics();
    useRuntimeStore.getState().reset();
  });

  it("renders against the live store", () => {
    renderWithProviders(<MetricsHeaderContainer />);
    expect(screen.getByRole("region", { name: /Runtime metrics/i })).toBeInTheDocument();
  });

  it("reflects realtime warning state", () => {
    renderWithProviders(<MetricsHeaderContainer />);
    expect(screen.getByText(/No active warnings/i)).toBeInTheDocument();

    act(() => {
      useRuntimeStore.setState({
        warnings: {
          warningsById: {
            w1: {
              warning_id: "w1",
              warning_key: "k",
              warning_type: "stuck_task",
              severity: "critical",
              message: "stuck",
              detector: "stuck",
              created_sequence: null,
              created_monotonic_ns: 0,
              created_at_wall: 0,
              last_observed_sequence: null,
              last_observed_monotonic_ns: 0,
              last_observed_wall: 0,
              occurrence_count: 1,
              resolved: false,
              resolved_sequence: null,
              resolved_monotonic_ns: null,
              resolved_at_wall: null,
              expired: false,
              related_task_ids: [],
              lineage_root_id: null,
              metadata: {},
              runtime_id: null,
            },
          },
          activeWarningIds: ["w1"],
          resolvedWarningIds: [],
          countsBySeverity: { info: 0, warning: 0, error: 0, critical: 1 },
        },
      });
    });

    expect(screen.queryByText(/No active warnings/i)).toBeNull();
    expect(screen.getByText(/C 1 · E 0 · W 0 · I 0/)).toBeInTheDocument();
  });

  it("records observability counters", () => {
    renderWithProviders(<MetricsHeaderContainer />);
    const snap = getMetricsHeaderMetrics().snapshot();
    expect(snap.projectionRebuilds).toBeGreaterThan(0);
    expect(snap.cardRenders).toBeGreaterThan(0);
  });
});
