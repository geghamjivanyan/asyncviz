/**
 * Declarative split-view primitive.
 *
 * Pure CSS today (no drag-resize) — supplies the composition contract
 * future resize-aware versions can swap into without consumers
 * re-wiring their layouts. Each :class:`DashboardSplitView.Pane` is a
 * named slot inside a flex container.
 *
 * Example::
 *
 *   <DashboardSplitView orientation="vertical">
 *     <DashboardSplitView.Pane size="primary">
 *       <TimelinePanel />
 *     </DashboardSplitView.Pane>
 *     <DashboardSplitView.Pane size="auxiliary" basis="14rem">
 *       <EventPanel />
 *     </DashboardSplitView.Pane>
 *   </DashboardSplitView>
 */

import { Children, isValidElement } from "react";
import type { CSSProperties, ReactElement, ReactNode } from "react";
import { cn } from "@/lib/cn";

export type SplitOrientation = "horizontal" | "vertical";
export type PaneSize = "primary" | "auxiliary" | "fixed";

export interface DashboardSplitViewProps {
  orientation: SplitOrientation;
  className?: string;
  children: ReactNode;
}

export interface DashboardSplitPaneProps {
  /** ``primary`` panes flex-grow; ``auxiliary`` panes are fixed-basis; ``fixed`` panes ignore flex. */
  size: PaneSize;
  /** When ``size`` is ``auxiliary`` or ``fixed`` — the basis value (e.g. ``"14rem"`` or ``"56px"``). */
  basis?: string;
  /** Optional minimum dimension along the split axis. */
  minSize?: string;
  className?: string;
  children: ReactNode;
}

function isPaneElement(node: ReactNode): node is ReactElement<DashboardSplitPaneProps> {
  return isValidElement(node) && node.type === DashboardSplitPane;
}

export function DashboardSplitView({ orientation, className, children }: DashboardSplitViewProps) {
  const isVertical = orientation === "vertical";
  return (
    <div
      role="group"
      aria-orientation={isVertical ? "vertical" : "horizontal"}
      className={cn("flex min-h-0 min-w-0", isVertical ? "flex-col" : "flex-row", className)}
    >
      {Children.map(children, (child) => {
        if (!isPaneElement(child)) return child;
        return child;
      })}
    </div>
  );
}

function DashboardSplitPane({
  size,
  basis,
  minSize,
  className,
  children,
}: DashboardSplitPaneProps) {
  const style: CSSProperties = {};
  if (basis !== undefined) {
    style.flexBasis = basis;
  }
  if (minSize !== undefined) {
    if (size === "fixed" || size === "auxiliary") {
      // For non-growing panes, ``minSize`` controls both axes via
      // ``min-height`` / ``min-width``; CSS picks the right one based
      // on the parent orientation we're flexed into. We set both so
      // either orientation Just Works.
      style.minHeight = minSize;
      style.minWidth = minSize;
    } else {
      style.minHeight = minSize;
      style.minWidth = minSize;
    }
  }

  return (
    <div
      style={style}
      className={cn(
        "flex min-h-0 min-w-0 flex-col",
        size === "primary" && "flex-1",
        size === "auxiliary" && "shrink-0",
        size === "fixed" && "shrink-0 grow-0",
        className,
      )}
    >
      {children}
    </div>
  );
}

DashboardSplitView.Pane = DashboardSplitPane;
