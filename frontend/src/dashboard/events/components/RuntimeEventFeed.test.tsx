/**
 * Integration tests for the canonical runtime event feed.
 *
 * The tests render :class:`RuntimeEventFeedContainer` against a live
 * :class:`useRuntimeStore`, mutate the store via its public API, and
 * assert that the feed reflects the change.
 */

import { describe, expect, it, beforeEach } from "vitest";
import { act } from "react";
import { fireEvent, screen, within } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { useRuntimeStore } from "@/state/runtime/store";
import { RuntimeEventFeedContainer } from "@/dashboard/events/components/RuntimeEventFeedContainer";
import { getEventFeedMetrics, resetEventFeedMetrics } from "@/dashboard/events/observability";
import type { RuntimeEnvelope, TaskLifecycleEvent } from "@/types/runtime";

function eventEnvelope(
  sequence: number,
  taskId: string,
  type: TaskLifecycleEvent["event_type"],
  overrides: Partial<TaskLifecycleEvent> = {},
): RuntimeEnvelope {
  const payload: TaskLifecycleEvent = {
    event_type: type,
    event_id: `evt-${sequence}`,
    timestamp: sequence,
    monotonic_timestamp: sequence,
    monotonic_ns: sequence * 1_000_000,
    runtime_id: "rt-1",
    source: "test",
    payload_version: 1,
    task_id: taskId,
    parent_task_id: null,
    coroutine_name: "fn",
    task_name: null,
    metadata: {},
    ...overrides,
  } as TaskLifecycleEvent;
  return {
    protocol_version: "1.0",
    type: "runtime_event",
    timestamp: sequence,
    sequence,
    payload: payload as unknown as Record<string, unknown>,
  };
}

describe("RuntimeEventFeedContainer", () => {
  beforeEach(() => {
    resetEventFeedMetrics();
    useRuntimeStore.getState().reset();
  });

  it("shows the empty state when no events", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    expect(screen.getByText(/No events/i)).toBeInTheDocument();
  });

  it("renders a row when an envelope is applied", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "alpha", "asyncio.task.started"));
    });
    expect(screen.getByRole("feed", { name: /Runtime event feed/i })).toBeInTheDocument();
    expect(screen.getByText("fn")).toBeInTheDocument();
  });

  it("renders rows newest-first by default", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore
        .getState()
        .applyEnvelope(eventEnvelope(1, "a", "asyncio.task.created", { coroutine_name: "alpha" }));
      useRuntimeStore
        .getState()
        .applyEnvelope(
          eventEnvelope(2, "a", "asyncio.task.completed", { coroutine_name: "alpha" }),
        );
    });
    const articles = screen.getAllByRole("article");
    // articles are <li role="article"> rows — first one is the newest.
    expect(articles[0]).toHaveAttribute("data-event-category", "task.completed");
  });

  it("toggles sort direction via the toolbar", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "a", "asyncio.task.created"));
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(2, "a", "asyncio.task.completed"));
    });
    const sortButton = screen.getByRole("button", { name: /Sort newest first/i });
    fireEvent.click(sortButton);
    const articles = screen.getAllByRole("article");
    expect(articles[0]).toHaveAttribute("data-event-category", "task.created");
  });

  it("filters by warnings-only", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "a", "asyncio.task.created"));
      useRuntimeStore.setState({
        warnings: {
          warningsById: {
            w1: {
              warning_id: "w1",
              warning_key: "k",
              warning_type: "stuck_task",
              severity: "warning",
              message: "m",
              detector: "d",
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
              related_task_ids: ["b"],
              lineage_root_id: null,
              metadata: {},
              runtime_id: null,
            },
          },
          activeWarningIds: ["w1"],
          resolvedWarningIds: [],
          countsBySeverity: { info: 0, warning: 1, error: 0, critical: 0 },
        },
      });
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(2, "b", "asyncio.task.started"));
    });
    const warningsToggle = screen.getByRole("button", { name: /Warnings/i });
    fireEvent.click(warningsToggle);
    const articles = screen.getAllByRole("article");
    expect(articles).toHaveLength(1);
    expect(articles[0]).toHaveAttribute("data-event-category", "task.started");
  });

  it("selects the task on row click", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore
        .getState()
        .applyEnvelope(eventEnvelope(1, "alpha", "asyncio.task.started", { task_name: "Worker" }));
    });
    fireEvent.click(screen.getByRole("button", { name: /Select task alpha/i }));
    expect(useRuntimeStore.getState().selectedTaskId).toBe("alpha");
  });

  it("supports keyboard activation (Enter selects task)", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "kbd", "asyncio.task.started"));
    });
    const row = screen.getAllByRole("article")[0]!;
    fireEvent.keyDown(row, { key: "Enter" });
    expect(useRuntimeStore.getState().selectedTaskId).toBe("kbd");
  });

  it("expands a row with the toggle button", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "expand", "asyncio.task.started"));
    });
    const row = screen.getAllByRole("article")[0]!;
    expect(row).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(within(row).getByRole("button", { name: /Expand event details/i }));
    expect(row).toHaveAttribute("aria-expanded", "true");
  });

  it("clears the events when the Clear button is pressed", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "alpha", "asyncio.task.started"));
    });
    expect(screen.getAllByRole("article")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("groups by task when the group select is set to task", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "a", "asyncio.task.started"));
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(2, "b", "asyncio.task.started"));
    });
    fireEvent.change(screen.getByRole("combobox", { name: /Group events/i }), {
      target: { value: "task" },
    });
    const groups = screen.getAllByRole("group", { name: /task /i });
    expect(groups.length).toBeGreaterThanOrEqual(2);
  });

  it("records observability counters", () => {
    renderWithProviders(<RuntimeEventFeedContainer />);
    act(() => {
      useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "a", "asyncio.task.started"));
    });
    const snap = getEventFeedMetrics().snapshot();
    expect(snap.projectionRebuilds).toBeGreaterThan(0);
    expect(snap.pipelineRuns).toBeGreaterThan(0);
    expect(snap.rowRenders).toBeGreaterThan(0);
  });
});
