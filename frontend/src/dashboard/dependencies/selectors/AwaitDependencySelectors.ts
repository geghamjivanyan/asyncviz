/**
 * Zustand selector hooks for :class:`AwaitDependencyStore`.
 */

import { useMemo } from "react";
import { useAwaitDependencyStore } from "@/dashboard/dependencies/AwaitDependencyStore";
import { projectDependencies } from "@/dashboard/dependencies/AwaitDependencyProjection";
import type {
  AwaitEdgeRecord,
  AwaitEdgeView,
  AwaitNodeRecord,
  AwaitNodeView,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";

export function useAwaitDependencyNodeRecords(): ReadonlyArray<AwaitNodeRecord> {
  const nodesById = useAwaitDependencyStore((s) => s.nodesById);
  const nodeIds = useAwaitDependencyStore((s) => s.nodeIds);
  return useMemo(
    () => nodeIds.map((id) => nodesById[id]).filter(Boolean),
    [nodesById, nodeIds],
  );
}

export function useAwaitDependencyEdgeRecords(): ReadonlyArray<AwaitEdgeRecord> {
  const edgesById = useAwaitDependencyStore((s) => s.edgesById);
  const edgeIds = useAwaitDependencyStore((s) => s.edgeIds);
  return useMemo(
    () => edgeIds.map((id) => edgesById[id]).filter(Boolean),
    [edgesById, edgeIds],
  );
}

export function useAwaitDependencyViews(): {
  nodes: AwaitNodeView[];
  edges: AwaitEdgeView[];
  alarmCount: number;
} {
  const nodeRecords = useAwaitDependencyNodeRecords();
  const edgeRecords = useAwaitDependencyEdgeRecords();
  return useMemo(
    () => projectDependencies({ nodes: nodeRecords, edges: edgeRecords }),
    [nodeRecords, edgeRecords],
  );
}

export function useSelectedAwaitNodeView(): AwaitNodeView | null {
  const selectedId = useAwaitDependencyStore((s) => s.selectedNodeId);
  const { nodes } = useAwaitDependencyViews();
  return useMemo(() => {
    if (selectedId === null) return null;
    return nodes.find((n) => n.id === selectedId) ?? null;
  }, [selectedId, nodes]);
}

export function useAwaitDependencyStats() {
  return useAwaitDependencyStore((s) => s.stats);
}

export function useAwaitDependencyStatus() {
  return useAwaitDependencyStore((s) => s.status);
}

export function useAwaitDependencyErrorMessage() {
  return useAwaitDependencyStore((s) => s.errorMessage);
}
