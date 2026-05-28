/**
 * Stateful container for the dependency graph panel.
 *
 * Wires the websocket bridge, selection routing, and frame projection.
 * Renders props onto :class:`AwaitDependencyGraph`.
 */

import { useCallback, useMemo } from "react";
import { useAwaitDependencyWebsocketBridge } from "@/dashboard/dependencies/hooks/useAwaitDependencyWebsocketBridge";
import { useAwaitDependencySelection } from "@/dashboard/dependencies/hooks/useAwaitDependencySelection";
import {
  useAwaitDependencyErrorMessage,
  useAwaitDependencyStatus,
  useAwaitDependencyViews,
} from "@/dashboard/dependencies/selectors/AwaitDependencySelectors";
import { AwaitDependencyGraph } from "@/dashboard/dependencies/AwaitDependencyGraph";
import { buildDependencyFrame } from "@/dashboard/dependencies/AwaitDependencyRenderer";

export interface AwaitDependencyGraphContainerProps {
  disableLiveUpdates?: boolean;
  className?: string;
  /** Viewport width / height — defaults to a generous box that fits the
   *  whole layout. The container could later swap in a measured ref for
   *  true viewport-based virtualization. */
  viewportWidth?: number;
  viewportHeight?: number;
}

export function AwaitDependencyGraphContainer({
  disableLiveUpdates = false,
  className,
  viewportWidth = 1600,
  viewportHeight = 800,
}: AwaitDependencyGraphContainerProps): JSX.Element {
  useAwaitDependencyWebsocketBridge({ enabled: !disableLiveUpdates });

  const { nodes, edges, alarmCount } = useAwaitDependencyViews();
  const { selectedNodeId, selectNode, revealNode } = useAwaitDependencySelection();
  const status = useAwaitDependencyStatus();
  const errorMessage = useAwaitDependencyErrorMessage();

  const frame = useMemo(
    () =>
      buildDependencyFrame({
        nodes,
        edges,
        viewport: { x: 0, y: 0, width: viewportWidth, height: viewportHeight },
      }),
    [nodes, edges, viewportWidth, viewportHeight],
  );

  const handleSelect = useCallback(
    (id: string | null, kind: "task" | "gather" | null) => {
      if (id === null || kind === null) {
        selectNode(null);
        return;
      }
      revealNode(id, kind);
    },
    [selectNode, revealNode],
  );

  const statusProps = useMemo(
    () => ({ status, errorMessage }),
    [status, errorMessage],
  );

  return (
    <AwaitDependencyGraph
      nodes={nodes}
      edges={edges}
      alarmCount={alarmCount}
      frame={frame}
      selectedNodeId={selectedNodeId}
      onSelectNode={handleSelect}
      status={statusProps}
      className={className}
    />
  );
}
