"""Synthetic topology-graph generator.

Produces a deterministic adjacency graph the topology storms feed
into the bounded topology view. The graph is a layered DAG so
traversals terminate in bounded time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from asyncviz.stress.utils.deterministic_rng import DeterministicRng

_DEFAULT_FANOUT: Final[int] = 4


@dataclass(frozen=True, slots=True)
class TopologyNode:
    node_id: str
    parent_ids: tuple[str, ...]
    depth: int


def generate_topology_storm(
    *,
    node_count: int,
    seed: int,
    fanout: int = _DEFAULT_FANOUT,
    depth: int = 8,
) -> tuple[TopologyNode, ...]:
    """Return a deterministic DAG."""
    if node_count < 0:
        raise ValueError(f"node_count must be >= 0 (got {node_count})")
    if fanout < 1:
        raise ValueError(f"fanout must be >= 1 (got {fanout})")
    if depth < 1:
        raise ValueError(f"depth must be >= 1 (got {depth})")
    rng = DeterministicRng(seed)
    layers: list[list[str]] = [[] for _ in range(depth)]
    nodes: list[TopologyNode] = []
    for index in range(node_count):
        layer = index % depth
        node_id = f"node-{index:08d}"
        parents: tuple[str, ...] = ()
        if layer > 0:
            candidates = layers[layer - 1]
            if candidates:
                count = min(fanout, len(candidates))
                parents = tuple(rng.choice(candidates) for _ in range(count))
        nodes.append(TopologyNode(node_id=node_id, parent_ids=parents, depth=layer))
        layers[layer].append(node_id)
    return tuple(nodes)
