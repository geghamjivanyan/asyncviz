import { describe, expect, it } from "vitest";
import {
  describeInspection,
  describePanelSwitch,
} from "@/dashboard/inspector/TaskInspectorAccessibility";
import { buildTaskInspection } from "@/dashboard/inspector/selectors/inspectionSelectors";
import { EMPTY_TASK_INSPECTION } from "@/dashboard/inspector/models/TaskInspectionModels";
import { makeTask, makeWarning } from "@/dashboard/inspector/__fixtures__/makeInspectionFixtures";

describe("inspector a11y helpers", () => {
  it("describes the empty inspection", () => {
    expect(describeInspection(EMPTY_TASK_INSPECTION)).toContain("No task selected");
  });

  it("describes a populated inspection", () => {
    const inspection = buildTaskInspection({
      task: makeTask("t1", { task_name: "Worker", state: "running" }),
      activeWarnings: [makeWarning("w1", ["t1"], "warning")],
    });
    const text = describeInspection(inspection);
    expect(text).toContain("Worker");
    expect(text).toContain("Running");
    expect(text).toContain("warning");
  });

  it("describes a panel switch", () => {
    expect(describePanelSwitch("metrics")).toContain("metrics");
  });
});
