/**
 * One-warning card.
 *
 * Header carries the severity + state badges + the freeze duration
 * summary. The body is the lifecycle summary in compact form. The
 * expanded body (inspector) is conditionally rendered when the card
 * is selected.
 *
 * Clicking the card toggles selection. The whole header is a button
 * so keyboard navigation works without a separate focus trap.
 */

import { memo, useCallback } from "react";
import { cn } from "@/lib/cn";
import { Card } from "@/ui/primitives/Card";
import type { BlockingWarningView } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { BlockingWarningInspector } from "@/dashboard/warnings/blocking/BlockingWarningInspector";
import { BlockingWarningLifecycleSummary } from "@/dashboard/warnings/blocking/BlockingWarningLifecycle";
import {
  BlockingWarningSeverityBadge,
  BlockingWarningStateBadge,
} from "@/dashboard/warnings/blocking/BlockingWarningSeverity";
import { freezeSummaryLabel, intentToken } from "@/dashboard/warnings/blocking/utils/formatting";
import { describeViewForAccessibility } from "@/dashboard/warnings/blocking/BlockingWarningAccessibility";

export interface BlockingWarningCardProps {
  view: BlockingWarningView;
  selected: boolean;
  onSelect: (groupId: string | null) => void;
  onSelectCapture?: (captureId: number, groupId: string) => void;
  onSelectTask?: (taskId: string) => void;
  className?: string;
}

function BlockingWarningCardImpl({
  view,
  selected,
  onSelect,
  onSelectCapture,
  onSelectTask,
  className,
}: BlockingWarningCardProps) {
  const intent = intentToken(view.intent);
  const handleToggle = useCallback(() => {
    onSelect(selected ? null : view.groupId);
  }, [onSelect, selected, view.groupId]);

  const accessibleLabel = describeViewForAccessibility(view);

  return (
    <Card
      intent={intent}
      padding="sm"
      className={cn(
        "transition-colors",
        view.isOpen ? "" : "opacity-80",
        selected ? "ring-2 ring-accent" : "",
        className,
      )}
      data-testid={`blocking-warning-card-${view.groupId}`}
      data-state={view.state}
      data-severity={view.severity}
      data-selected={selected ? "true" : "false"}
      aria-current={selected ? "true" : undefined}
    >
      <button
        type="button"
        onClick={handleToggle}
        className="flex w-full flex-col gap-2 text-left"
        aria-expanded={selected}
        aria-label={accessibleLabel}
        data-testid={`blocking-warning-card-toggle-${view.groupId}`}
      >
        <header className="flex flex-wrap items-center gap-2">
          <BlockingWarningStateBadge state={view.state} intent={view.intent} />
          <BlockingWarningSeverityBadge severity={view.severity} intent={view.intent} />
          {view.peakSeverity !== view.severity && (
            <span
              className="text-subtle text-xs font-mono"
              aria-label={`Peak severity reached ${view.peakSeverity}`}
              data-testid={`blocking-warning-peak-${view.groupId}`}
            >
              peak: {view.peakSeverity}
            </span>
          )}
          <span className="ml-auto text-xs font-mono text-text">
            {freezeSummaryLabel(view.freezeDurationMs, view.captureIds.length)}
          </span>
        </header>
        <div className="text-xs font-mono text-subtle">
          {view.windowId !== null ? (
            <span>
              window <span className="text-text">{view.windowId}</span>
            </span>
          ) : (
            <span>no-window bucket</span>
          )}
          {view.taskName !== null && (
            <>
              <span className="mx-2">·</span>
              <span>
                task <span className="text-text">{view.taskName}</span>
              </span>
            </>
          )}
        </div>
        {!selected && <BlockingWarningLifecycleSummary view={view} />}
      </button>
      {selected && (
        <div className="mt-3 border-t border-line pt-3">
          <BlockingWarningInspector
            view={view}
            onSelectCapture={onSelectCapture}
            onSelectTask={onSelectTask}
          />
        </div>
      )}
    </Card>
  );
}

export const BlockingWarningCard = memo(BlockingWarningCardImpl);
