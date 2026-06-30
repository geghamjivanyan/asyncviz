import { describe, expect, it } from "vitest";
import { isFrameworkTask } from "@/dashboard/tasks/models/frameworkTasks";

describe("isFrameworkTask", () => {
  it("flags Starlette middleware tasks", () => {
    expect(
      isFrameworkTask({
        coroutineName: "BaseHTTPMiddleware.__call__.<locals>.call_next.<locals>.coro",
        taskName:
          "starlette.middleware.base.BaseHTTPMiddleware.__call__.<locals>.call_next.<locals>.coro",
      }),
    ).toBe(true);
  });

  it("flags Uvicorn / ASGI prefixes", () => {
    expect(isFrameworkTask({ coroutineName: "uvicorn.protocols.serve", taskName: null })).toBe(
      true,
    );
    expect(isFrameworkTask({ coroutineName: null, taskName: "asgi.lifespan.startup" })).toBe(true);
  });

  it("flags AsyncViz internal bookkeeping tasks", () => {
    expect(
      isFrameworkTask({ coroutineName: "_heartbeat_loop", taskName: "asyncviz-heartbeat" }),
    ).toBe(true);
    expect(isFrameworkTask({ coroutineName: "asyncviz.dashboard.runtime", taskName: null })).toBe(
      true,
    );
  });

  it("does NOT flag user coroutines", () => {
    expect(isFrameworkTask({ coroutineName: "heartbeat", taskName: "heartbeat" })).toBe(false);
    expect(isFrameworkTask({ coroutineName: "worker", taskName: "worker-1" })).toBe(false);
    expect(isFrameworkTask({ coroutineName: "parent_with_children", taskName: "parent" })).toBe(
      false,
    );
    expect(isFrameworkTask({ coroutineName: "semaphore_worker", taskName: "sem-worker-3" })).toBe(
      false,
    );
  });

  it("handles empty / null names", () => {
    expect(isFrameworkTask({ coroutineName: null, taskName: null })).toBe(false);
    expect(isFrameworkTask({ coroutineName: "", taskName: "" })).toBe(false);
  });

  it("does NOT flag user coroutines whose name happens to contain a substring elsewhere", () => {
    // A user coroutine named ``starletteAdmin`` shouldn't trip the
    // prefix match (which anchors on ``starlette.``).
    expect(isFrameworkTask({ coroutineName: "starletteAdmin", taskName: "starletteAdmin" })).toBe(
      false,
    );
  });
});
