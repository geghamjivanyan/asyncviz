import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { AwaitDependencyGraph } from "@/dashboard/dependencies/AwaitDependencyGraph";
import { projectDependencies } from "@/dashboard/dependencies/AwaitDependencyProjection";
import { buildDependencyFrame } from "@/dashboard/dependencies/AwaitDependencyRenderer";
import {
  makeEdge,
  makeNode,
} from "@/dashboard/dependencies/__fixtures__/awaitDependencyFixtures";

function renderGraph({
  nodes,
  edges,
  selectedNodeId = null,
  onSelectNode = vi.fn(),
}: {
  nodes: ReturnType<typeof makeNode>[];
  edges: ReturnType<typeof makeEdge>[];
  selectedNodeId?: string | null;
  onSelectNode?: (id: string | null, kind: "task" | "gather" | null) => void;
}) {
  const { nodes: views, edges: edgeViews, alarmCount } = projectDependencies({
    nodes,
    edges,
  });
  const frame = buildDependencyFrame({
    nodes: views,
    edges: edgeViews,
    viewport: { x: 0, y: 0, width: 2000, height: 1000 },
  });
  return {
    onSelectNode,
    ...render(
      <AwaitDependencyGraph
        nodes={views}
        edges={edgeViews}
        alarmCount={alarmCount}
        frame={frame}
        selectedNodeId={selectedNodeId}
        onSelectNode={onSelectNode}
        status={{ status: "ready", errorMessage: null }}
      />,
    ),
  };
}

describe("<AwaitDependencyGraph />", () => {
  it("renders the empty state when no nodes are tracked", () => {
    renderGraph({ nodes: [], edges: [] });
    expect(screen.getByTestId("await-dependency-empty")).toBeInTheDocument();
  });

  it("renders a node per record + draws edges", () => {
    renderGraph({
      nodes: [
        makeNode({ id: "t-root", kind: "task" }),
        makeNode({ id: "g-1", kind: "gather", parentTaskId: "t-root" }),
        makeNode({ id: "t-leaf", kind: "task" }),
      ],
      edges: [
        makeEdge({ id: "awaits:t-root->g-1", kind: "awaits", fromId: "t-root", toId: "g-1" }),
        makeEdge({ id: "fanout:g-1->t-leaf", fromId: "g-1", toId: "t-leaf" }),
      ],
    });
    expect(screen.getAllByTestId("await-dependency-node")).toHaveLength(3);
    expect(screen.getAllByTestId("await-dependency-edge")).toHaveLength(2);
  });

  it("invokes onSelectNode with id + kind on click", async () => {
    const onSelect = vi.fn();
    renderGraph({
      nodes: [makeNode({ id: "t-1", kind: "task" })],
      edges: [],
      onSelectNode: onSelect,
    });
    const user = userEvent.setup();
    await user.click(screen.getByTestId("await-dependency-node"));
    expect(onSelect).toHaveBeenCalledWith("t-1", "task");
  });

  it("announces topology composition via the live region", () => {
    renderGraph({
      nodes: [
        makeNode({ id: "t-1", kind: "task" }),
        makeNode({ id: "g-1", kind: "gather" }),
      ],
      edges: [],
    });
    expect(screen.getByTestId("await-dependency-live-region")).toHaveTextContent(
      /2 nodes/,
    );
  });

  it("counts non-calm gathers in the alarm badge", () => {
    renderGraph({
      nodes: [
        makeNode({ id: "g-ok", kind: "gather", state: "completed" }),
        makeNode({ id: "g-bad", kind: "gather", state: "failed" }),
      ],
      edges: [],
    });
    expect(screen.getByTestId("await-dependency-alarm-count")).toHaveTextContent(
      /1 alarm/,
    );
  });
});
