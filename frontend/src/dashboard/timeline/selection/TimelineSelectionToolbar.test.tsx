import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TimelineSelectionToolbar } from "@/dashboard/timeline/selection/TimelineSelectionToolbar";
import { TimelineSelectionController } from "@/dashboard/timeline/selection/TimelineSelectionController";
import {
  makeInMemoryStore,
  makeRows,
  makeTask,
} from "@/dashboard/timeline/selection/__fixtures__/makeSelectionFixtures";

function buildController(options: { initial?: string | null } = {}) {
  const store = makeInMemoryStore(options.initial ?? null);
  const rows = makeRows(3);
  const taskMap = new Map(rows.map((r) => [r.taskId, makeTask(r.taskId)]));
  return new TimelineSelectionController({
    store,
    rows: {
      getRows: () => rows,
      getTask: (id) => (id === null ? null : (taskMap.get(id) ?? null)),
      getTaskRange: () => ({ startSeconds: 0, endSeconds: 1 }),
    },
  });
}

describe("TimelineSelectionToolbar", () => {
  it("renders a placeholder when controller is null", () => {
    render(<TimelineSelectionToolbar controller={null} state={null} />);
    expect(screen.getByText(/Selection controls unavailable/)).toBeInTheDocument();
  });

  it("renders prev / next / center / clear buttons", () => {
    const controller = buildController({ initial: "t1" });
    render(
      <TimelineSelectionToolbar
        controller={controller}
        state={controller.currentState()}
      />,
    );
    expect(screen.getByLabelText("Select previous row")).toBeInTheDocument();
    expect(screen.getByLabelText("Select next row")).toBeInTheDocument();
    expect(screen.getByLabelText("Clear selection")).toBeInTheDocument();
    expect(screen.getByLabelText("Center on selection")).toBeInTheDocument();
  });

  it("clicking ↓ moves the selection to the next row", async () => {
    const controller = buildController({ initial: "t0" });
    const user = userEvent.setup();
    render(
      <TimelineSelectionToolbar
        controller={controller}
        state={controller.currentState()}
      />,
    );
    await user.click(screen.getByLabelText("Select next row"));
    expect(controller.currentState().selectedTaskId).toBe("t1");
  });

  it("disables clear when nothing is selected", () => {
    const controller = buildController();
    render(
      <TimelineSelectionToolbar
        controller={controller}
        state={controller.currentState()}
      />,
    );
    expect(screen.getByLabelText("Clear selection")).toBeDisabled();
  });

  it("disables prev when at first + next when at last", () => {
    const first = buildController({ initial: "t0" });
    const last = buildController({ initial: "t2" });
    const { unmount } = render(
      <TimelineSelectionToolbar
        controller={first}
        state={first.currentState()}
      />,
    );
    expect(screen.getByLabelText("Select previous row")).toBeDisabled();
    unmount();
    render(
      <TimelineSelectionToolbar
        controller={last}
        state={last.currentState()}
      />,
    );
    expect(screen.getByLabelText("Select next row")).toBeDisabled();
  });
});
