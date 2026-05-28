/**
 * Pure SR announcement formatters for the task inspector.
 */

import {
  formatDuration,
  formatLifecycleState,
  shortenIdentifier,
} from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

/** Pure: describe the active inspection state. */
export function describeInspection(inspection: TaskInspection): string {
  if (inspection.task === null) {
    return "No task selected.";
  }
  const task = inspection.task;
  const label = task.task_name ?? task.coroutine_name ?? shortenIdentifier(task.task_id);
  const state = formatLifecycleState(inspection.state);
  const duration = formatDuration(inspection.lifecycle.durationSeconds);
  const segments = inspection.timeline.segmentCount;
  const warnings =
    inspection.warnings.count > 0
      ? `, ${inspection.warnings.count} ${inspection.warnings.highestSeverity ?? "active"} warning${inspection.warnings.count === 1 ? "" : "s"}`
      : "";
  return `Inspecting ${label}: state ${state}, ${segments} segment${segments === 1 ? "" : "s"}, duration ${duration}${warnings}.`;
}

/** Pure: describe a panel switch event. */
export function describePanelSwitch(panel: string): string {
  return `Switched to ${panel} panel.`;
}
