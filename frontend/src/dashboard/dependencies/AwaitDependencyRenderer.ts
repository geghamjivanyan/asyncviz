/**
 * Pure frame builder for the await dependency graph.
 *
 * Combines projection + layout + virtualization into a single
 * deterministic ``layoutFrame`` entry point. The canvas component
 * consumes the output; tests exercise the same surface.
 */

import {
  virtualize,
  type VirtualizationOutput,
} from "@/dashboard/dependencies/AwaitDependencyVirtualization";
import {
  layoutDependencies,
  type LayoutFrame,
  type LayoutInputs,
} from "@/dashboard/dependencies/layout/AwaitDependencyLayout";
import { getAwaitDependencyPanelMetrics } from "@/dashboard/dependencies/diagnostics/AwaitDependencyMetricsCollector";
import { recordAwaitDependencyTrace } from "@/dashboard/dependencies/diagnostics/AwaitDependencyTracing";
import type { Viewport } from "@/dashboard/dependencies/AwaitDependencyGeometry";

export interface DependencyFrameInputs extends LayoutInputs {
  viewport: Viewport;
  maxNodes?: number;
  maxEdges?: number;
}

export interface DependencyFrame extends VirtualizationOutput {
  layout: LayoutFrame;
}

export function buildDependencyFrame(inputs: DependencyFrameInputs): DependencyFrame {
  const layout = layoutDependencies(inputs);
  getAwaitDependencyPanelMetrics().recordLayoutComputed();
  recordAwaitDependencyTrace({
    kind: "layout-computed",
    detail: `nodes=${layout.laidNodes.length} edges=${layout.laidEdges.length}`,
  });
  const virtualization = virtualize({
    frame: layout,
    viewport: inputs.viewport,
    maxNodes: inputs.maxNodes,
    maxEdges: inputs.maxEdges,
  });
  getAwaitDependencyPanelMetrics().recordNodesRendered(virtualization.visibleNodes.length);
  getAwaitDependencyPanelMetrics().recordEdgesRendered(virtualization.visibleEdges.length);
  return { ...virtualization, layout };
}
