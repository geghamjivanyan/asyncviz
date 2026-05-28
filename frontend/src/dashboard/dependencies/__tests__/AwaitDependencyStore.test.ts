import { beforeEach, describe, expect, it } from "vitest";
import { useAwaitDependencyStore } from "@/dashboard/dependencies/AwaitDependencyStore";
import {
  makeChildAttached,
  makeChildCompleted,
  makeGatherCancelled,
  makeGatherCompleted,
  makeGatherCreated,
  makeGatherFailed,
  makeWaitStarted,
} from "@/dashboard/dependencies/__fixtures__/awaitDependencyFixtures";

beforeEach(() => {
  useAwaitDependencyStore.getState().reset();
});

describe("AwaitDependencyStore reducers", () => {
  it("gather.created scaffolds parent + gather + child nodes and wires edges", () => {
    useAwaitDependencyStore.getState().applyEventPayload(
      makeGatherCreated({
        gather_id: "g-1",
        parent_task_id: "t-parent",
        child_task_ids: ["t-a", "t-b"],
      }),
    );
    const s = useAwaitDependencyStore.getState();
    expect(Object.keys(s.nodesById).sort()).toEqual([
      "g-1", "t-a", "t-b", "t-parent",
    ]);
    expect(s.edgeIds).toContain("awaits:t-parent->g-1");
    expect(s.edgeIds).toContain("fanout:g-1->t-a");
    expect(s.edgeIds).toContain("fanout:g-1->t-b");
  });

  it("child.attached is idempotent on edges", () => {
    const store = useAwaitDependencyStore.getState();
    store.applyEventPayload(makeGatherCreated());
    store.applyEventPayload(makeChildAttached({ child_task_id: "t-c1" }));
    store.applyEventPayload(makeChildAttached({ child_task_id: "t-c1" }));
    const s = useAwaitDependencyStore.getState();
    const matches = s.edgeIds.filter((id) => id === "fanout:g-1->t-c1");
    expect(matches.length).toBe(1);
  });

  it("wait.started moves gather node to running", () => {
    const store = useAwaitDependencyStore.getState();
    store.applyEventPayload(makeGatherCreated());
    expect(useAwaitDependencyStore.getState().nodesById["g-1"]?.state).toBe(
      "pending",
    );
    store.applyEventPayload(makeWaitStarted());
    expect(useAwaitDependencyStore.getState().nodesById["g-1"]?.state).toBe(
      "running",
    );
  });

  it("child.completed updates child state + marks fanout edge", () => {
    const store = useAwaitDependencyStore.getState();
    store.applyEventPayload(makeGatherCreated());
    store.applyEventPayload(
      makeChildCompleted({
        child_task_id: "t-c1",
        failed: true,
        cancelled: false,
        completed_count: 1,
      }),
    );
    const s = useAwaitDependencyStore.getState();
    expect(s.nodesById["t-c1"]?.state).toBe("failed");
    expect(s.edgesById["fanout:g-1->t-c1"]?.failed).toBe(true);
    expect(s.nodesById["g-1"]?.completedCount).toBe(1);
    expect(s.nodesById["g-1"]?.failedCount).toBe(1);
  });

  it("gather.completed marks gather as completed with duration", () => {
    const store = useAwaitDependencyStore.getState();
    store.applyEventPayload(makeGatherCreated());
    store.applyEventPayload(
      makeGatherCompleted({ completed_count: 2, duration_seconds: 0.5 }),
    );
    const node = useAwaitDependencyStore.getState().nodesById["g-1"];
    expect(node?.state).toBe("completed");
    expect(node?.durationSeconds).toBe(0.5);
  });

  it("gather.cancelled marks gather as cancelled", () => {
    const store = useAwaitDependencyStore.getState();
    store.applyEventPayload(makeGatherCreated());
    store.applyEventPayload(makeGatherCancelled());
    expect(useAwaitDependencyStore.getState().nodesById["g-1"]?.state).toBe(
      "cancelled",
    );
  });

  it("gather.failed captures the exception type", () => {
    const store = useAwaitDependencyStore.getState();
    store.applyEventPayload(makeGatherCreated());
    store.applyEventPayload(
      makeGatherFailed({ exception_type: "RuntimeError" }),
    );
    const node = useAwaitDependencyStore.getState().nodesById["g-1"];
    expect(node?.state).toBe("failed");
    expect(node?.exceptionType).toBe("RuntimeError");
  });

  it("respects maxNodes cap and reports evictions", () => {
    useAwaitDependencyStore.getState().setMaxNodes(2);
    useAwaitDependencyStore.getState().applyEventPayload(
      makeGatherCreated({
        parent_task_id: "t-p",
        child_task_ids: ["t-a", "t-b", "t-c"],
      }),
    );
    const s = useAwaitDependencyStore.getState();
    expect(s.nodeIds.length).toBeLessThanOrEqual(2);
    expect(s.stats.nodesEvicted).toBeGreaterThan(0);
  });
});
