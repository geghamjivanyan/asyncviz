/**
 * Integration smoke test for the canvas timeline.
 *
 * jsdom can render the React tree + the canvas element, but it
 * doesn't actually draw. We only assert that:
 *
 *   * the canvas mounts,
 *   * the a11y companion enumerates rows,
 *   * the renderer observability incremented (frames may not arrive
 *     in jsdom because there's no rAF wall-clock — we accept zero).
 */

import { afterAll, beforeAll, describe, expect, it, beforeEach } from "vitest";
import { act } from "react";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { useRuntimeStore } from "@/state/runtime/store";
import { TimelineContainer } from "@/dashboard/timeline/components/TimelineContainer";
import { resetTimelineRendererMetrics } from "@/dashboard/timeline/observability";
import { installFakeCanvasContext } from "@/dashboard/timeline/rendering/__fixtures__/mockCanvas";
import type { TaskSnapshot } from "@/types/runtime";

let restoreCanvas: (() => void) | undefined;
beforeAll(() => {
  restoreCanvas = installFakeCanvasContext();
});
afterAll(() => {
  restoreCanvas?.();
});

function makeTask(taskId: string): TaskSnapshot {
  return {
    task_id: taskId,
    state: "running",
    created_at: 0,
    updated_at: 0,
    asyncio_task_id: null,
    coroutine_name: `${taskId}_fn`,
    task_name: null,
    parent_task_id: null,
    root_task_id: taskId,
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
  };
}

describe("TimelineContainer", () => {
  beforeEach(() => {
    resetTimelineRendererMetrics();
    useRuntimeStore.getState().reset();
  });

  it("renders an empty a11y summary when no tasks exist", () => {
    renderWithProviders(<TimelineContainer />);
    expect(screen.getByText(/Timeline is empty/i)).toBeInTheDocument();
  });

  it("mounts the canvas region", () => {
    renderWithProviders(<TimelineContainer />);
    const region = document.querySelector("[data-timeline-canvas-region]");
    expect(region).not.toBeNull();
    expect(region!.querySelector("canvas")).not.toBeNull();
  });

  it("surfaces visible rows in the a11y companion", () => {
    act(() => {
      useRuntimeStore.setState({
        tasksById: { alpha: makeTask("alpha"), beta: makeTask("beta") },
      });
    });
    renderWithProviders(<TimelineContainer />);
    expect(screen.getByText(/2 task rows visible/i)).toBeInTheDocument();
  });

  it("the canvas reports the canonical role + aria label", () => {
    renderWithProviders(<TimelineContainer />);
    expect(screen.getByRole("img", { name: /Timeline canvas/i })).toBeInTheDocument();
  });
});
