/**
 * Tab toolbar — switches between the inspector panels.
 */

import { memo, useMemo } from "react";
import { cn } from "@/lib/cn";
import {
  INSPECTOR_PANEL_ORDER,
  type InspectorPanelKind,
} from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorToolbarProps {
  activePanel: InspectorPanelKind;
  onSelect: (kind: InspectorPanelKind) => void;
  /** Optional badge counts shown next to panel labels. */
  badges?: Partial<Record<InspectorPanelKind, number>>;
  className?: string;
}

const PANEL_LABELS: Record<InspectorPanelKind, string> = {
  overview: "Overview",
  timeline: "Timeline",
  metrics: "Metrics",
  warnings: "Warnings",
  relationships: "Tree",
  events: "Events",
  replay: "Replay",
  lifecycle: "Lifecycle",
  metadata: "Metadata",
  diagnostics: "Diagnostics",
};

function TaskInspectorToolbarImpl({
  activePanel,
  onSelect,
  badges,
  className,
}: TaskInspectorToolbarProps) {
  const panels = useMemo(() => INSPECTOR_PANEL_ORDER, []);
  return (
    <nav
      data-task-inspector-toolbar="true"
      role="tablist"
      aria-label="Task inspector panels"
      className={cn(
        "flex flex-wrap gap-1 border-b border-line bg-panel px-2 py-1",
        className,
      )}
    >
      {panels.map((kind) => {
        const isActive = kind === activePanel;
        const badge = badges?.[kind];
        return (
          <button
            key={kind}
            role="tab"
            type="button"
            aria-selected={isActive}
            data-inspector-tab={kind}
            onClick={() => onSelect(kind)}
            className={cn(
              "relative rounded border px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-widest transition-colors",
              isActive
                ? "border-accent bg-accent/15 text-accent"
                : "border-transparent font-normal text-muted hover:border-line hover:bg-elevated hover:text-text",
            )}
          >
            {PANEL_LABELS[kind]}
            {badge !== undefined && badge > 0 ? (
              <span
                className={cn(
                  "ml-1 rounded px-1 text-[10px]",
                  isActive ? "bg-warning/20 text-warning" : "text-warning",
                )}
              >
                {badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}

export const TaskInspectorToolbar = memo(TaskInspectorToolbarImpl);
