/**
 * Integration tests for the canonical task table.
 *
 * The tests render :class:`TaskTableContainer` against a live
 * :class:`useRuntimeStore`, mutate the store via its public API, and
 * assert that the table reflects the change. This pins down:
 *
 *   * realtime row updates
 *   * deterministic ordering
 *   * selection synchronization
 *   * sort / filter behavior
 *   * accessibility semantics (``role="grid"``, ``aria-selected``,
 *     ``aria-sort``)
 */

import { act } from "react";
import { describe, expect, it, beforeEach } from "vitest";
import { fireEvent, screen, within } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { useRuntimeStore } from "@/state/runtime/store";
import { TaskTableContainer } from "@/dashboard/tasks/components/TaskTableContainer";
import { resetTaskTableMetrics, getTaskTableMetrics } from "@/dashboard/tasks/observability";
import type { RuntimeEnvelope, TaskSnapshot } from "@/types/runtime";

function task(overrides: Partial<TaskSnapshot> & { task_id: string }): TaskSnapshot {
  return {
    state: "running",
    created_at: 0,
    updated_at: 0,
    asyncio_task_id: null,
    coroutine_name: null,
    task_name: null,
    parent_task_id: null,
    root_task_id: overrides.task_id,
    depth: 0,
    ancestor_chain: [],
    child_count: 0,
    completed_at: null,
    duration_seconds: null,
    exception_type: null,
    exception_message: null,
    cancellation_origin: null,
    runtime_id: "rt-1",
    tags: {},
    metadata: {},
    ...overrides,
  };
}

function seedStore(tasks: TaskSnapshot[]) {
  // We bypass the snapshot reducer and seed the normalized projections
  // directly — the store is a black box for this test.
  const store = useRuntimeStore.getState();
  store.reset();
  useRuntimeStore.setState({
    tasksById: Object.fromEntries(tasks.map((t) => [t.task_id, t])),
    taskIdsByState: {
      created: tasks.filter((t) => t.state === "created").map((t) => t.task_id),
      running: tasks.filter((t) => t.state === "running").map((t) => t.task_id),
      waiting: tasks.filter((t) => t.state === "waiting").map((t) => t.task_id),
      completed: tasks.filter((t) => t.state === "completed").map((t) => t.task_id),
      cancelled: tasks.filter((t) => t.state === "cancelled").map((t) => t.task_id),
      failed: tasks.filter((t) => t.state === "failed").map((t) => t.task_id),
    },
  });
}

describe("TaskTableContainer", () => {
  beforeEach(() => {
    resetTaskTableMetrics();
    useRuntimeStore.getState().reset();
  });

  it("renders one row per task with the canonical grid semantics", () => {
    seedStore([
      task({ task_id: "alpha", coroutine_name: "alpha_fn", created_at: 1 }),
      task({ task_id: "beta", coroutine_name: "beta_fn", created_at: 2 }),
    ]);
    renderWithProviders(<TaskTableContainer />);
    const grid = screen.getByRole("grid");
    expect(grid).toBeInTheDocument();
    const rows = within(grid).getAllByRole("row");
    // Header row + 2 data rows.
    expect(rows).toHaveLength(3);
  });

  it("shows the empty state when there are no tasks", () => {
    seedStore([]);
    renderWithProviders(<TaskTableContainer />);
    expect(screen.getByText(/No tasks/i)).toBeInTheDocument();
  });

  it("reflects realtime updates when a task transitions", () => {
    seedStore([task({ task_id: "a", state: "running", created_at: 1 })]);
    renderWithProviders(<TaskTableContainer />);
    expect(screen.getByText(/running/i)).toBeInTheDocument();

    act(() => {
      const envelope: RuntimeEnvelope = {
        protocol_version: "1.0",
        type: "runtime_event",
        timestamp: 0,
        sequence: 1,
        payload: {
          event_type: "asyncio.task.completed",
          event_id: "evt-1",
          timestamp: 0,
          monotonic_timestamp: 0,
          monotonic_ns: 0,
          runtime_id: "rt-1",
          source: "test",
          payload_version: 1,
          task_id: "a",
          parent_task_id: null,
          coroutine_name: null,
          task_name: null,
          metadata: {},
          created_at: 0,
          completed_at: 1,
          duration_seconds: 1,
        } as unknown as Record<string, unknown>,
      };
      useRuntimeStore.getState().applyEnvelope(envelope);
    });

    expect(screen.getByText(/completed/i)).toBeInTheDocument();
  });

  it("selects a task on click and syncs with the store", () => {
    seedStore([task({ task_id: "a", task_name: "WorkerA", created_at: 1 })]);
    renderWithProviders(<TaskTableContainer />);
    const row = screen.getByText("WorkerA").closest("[role=row]");
    expect(row).not.toBeNull();
    fireEvent.click(row!);
    expect(useRuntimeStore.getState().selectedTaskId).toBe("a");
    expect(row).toHaveAttribute("aria-selected", "true");
  });

  it("supports keyboard selection (Enter)", () => {
    seedStore([task({ task_id: "k", task_name: "Keyboard", created_at: 1 })]);
    renderWithProviders(<TaskTableContainer />);
    const row = screen.getByText("Keyboard").closest("[role=row]")!;
    fireEvent.keyDown(row, { key: "Enter" });
    expect(useRuntimeStore.getState().selectedTaskId).toBe("k");
  });

  it("filters by search text", () => {
    seedStore([
      task({ task_id: "a", task_name: "Alpha", created_at: 1 }),
      task({ task_id: "b", task_name: "Beta", created_at: 2 }),
    ]);
    renderWithProviders(<TaskTableContainer />);
    const input = screen.getByLabelText(/Filter tasks/i);
    fireEvent.change(input, { target: { value: "alpha" } });
    expect(screen.queryByText("Beta")).toBeNull();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });

  it("toggles sort direction when a column header is clicked", () => {
    seedStore([
      task({ task_id: "a", task_name: "Alpha", created_at: 5 }),
      task({ task_id: "b", task_name: "Beta", created_at: 10 }),
    ]);
    renderWithProviders(<TaskTableContainer />);
    const header = screen.getByRole("columnheader", { name: /Start time/i });
    // Default sort is started/desc — toggling should produce started/asc.
    fireEvent.click(header);
    expect(header).toHaveAttribute("aria-sort", "ascending");
  });

  it("toolbar 'Active' toggle prunes rows without an open segment", () => {
    seedStore([task({ task_id: "a", task_name: "Alpha", created_at: 1 })]);
    renderWithProviders(<TaskTableContainer />);
    const toggle = screen.getByRole("button", { name: /^Active$/ });
    fireEvent.click(toggle);
    expect(screen.queryByText("Alpha")).toBeNull();
  });

  it("records selection observability", () => {
    seedStore([task({ task_id: "a", task_name: "Alpha", created_at: 1 })]);
    renderWithProviders(<TaskTableContainer />);
    const row = screen.getByText("Alpha").closest("[role=row]")!;
    fireEvent.click(row);
    expect(getTaskTableMetrics().snapshot().selectionEvents).toBeGreaterThan(0);
  });
});
