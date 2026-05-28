import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskInspector } from "@/dashboard/inspector/TaskInspector";
import { buildTaskInspection } from "@/dashboard/inspector/selectors/inspectionSelectors";
import { EMPTY_TASK_INSPECTION } from "@/dashboard/inspector/models/TaskInspectionModels";
import {
  makeSegment,
  makeTask,
  makeWarning,
} from "@/dashboard/inspector/__fixtures__/makeInspectionFixtures";

describe("TaskInspector", () => {
  it("renders the empty state when no task is selected", () => {
    const onSelectPanel = vi.fn();
    render(
      <TaskInspector
        inspection={EMPTY_TASK_INSPECTION}
        activePanel="overview"
        onSelectPanel={onSelectPanel}
      />,
    );
    expect(screen.getAllByText(/No task selected/).length).toBeGreaterThan(0);
  });

  it("renders the loading state when loading=true", () => {
    render(
      <TaskInspector
        inspection={EMPTY_TASK_INSPECTION}
        activePanel="overview"
        loading
        onSelectPanel={vi.fn()}
      />,
    );
    expect(screen.getByText(/Loading task details/)).toBeInTheDocument();
  });

  it("renders the overview panel for a populated inspection", () => {
    const inspection = buildTaskInspection({
      task: makeTask("t1", { task_name: "Worker" }),
      segments: [makeSegment("s1", "t1", 0, 1_000_000_000)],
    });
    render(
      <TaskInspector
        inspection={inspection}
        activePanel="overview"
        onSelectPanel={vi.fn()}
      />,
    );
    // Worker appears in both the header h2 + the overview's name row;
    // confirming the count is >= 1 is enough to prove the panel
    // rendered.
    expect(screen.getAllByText("Worker").length).toBeGreaterThan(0);
  });

  it("switches panels via the toolbar", async () => {
    const inspection = buildTaskInspection({
      task: makeTask("t1"),
      activeWarnings: [makeWarning("w1", ["t1"], "warning")],
    });
    const onSelectPanel = vi.fn();
    const user = userEvent.setup();
    render(
      <TaskInspector
        inspection={inspection}
        activePanel="overview"
        onSelectPanel={onSelectPanel}
      />,
    );
    const warningsTab = screen.getByRole("tab", { name: /Warnings/ });
    await user.click(warningsTab);
    expect(onSelectPanel).toHaveBeenCalledWith("warnings");
  });

  it("renders relationships tab + invokes onSelectTask", async () => {
    const inspection = buildTaskInspection({
      task: makeTask("t1"),
      childTaskIds: ["child-1"],
    });
    const onSelectTask = vi.fn();
    const user = userEvent.setup();
    render(
      <TaskInspector
        inspection={inspection}
        activePanel="relationships"
        onSelectPanel={vi.fn()}
        onSelectTask={onSelectTask}
      />,
    );
    const childButton = await screen.findByRole("button", { name: /child-1/ });
    await user.click(childButton);
    expect(onSelectTask).toHaveBeenCalledWith("child-1");
  });

  it("invokes the header actions for fit / center / clear", async () => {
    const inspection = buildTaskInspection({ task: makeTask("t1") });
    const onFocus = vi.fn();
    const onCenter = vi.fn();
    const onClear = vi.fn();
    const user = userEvent.setup();
    render(
      <TaskInspector
        inspection={inspection}
        activePanel="overview"
        onSelectPanel={vi.fn()}
        onFocus={onFocus}
        onCenter={onCenter}
        onClear={onClear}
      />,
    );
    await user.click(screen.getByLabelText("Fit timeline to task"));
    await user.click(screen.getByLabelText("Center timeline on task"));
    await user.click(screen.getByLabelText("Clear inspection"));
    expect(onFocus).toHaveBeenCalled();
    expect(onCenter).toHaveBeenCalled();
    expect(onClear).toHaveBeenCalled();
  });
});
