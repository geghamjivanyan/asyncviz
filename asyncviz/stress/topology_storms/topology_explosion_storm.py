"""Topology-explosion storm.

Generates a DAG with ``topology_node_explosion`` nodes + records
adjacency invariants. Used to verify the bounded topology view
clamps memory + the LRU eviction is deterministic.
"""

from __future__ import annotations

from asyncviz.stress.harness.scenario_context import ScenarioContext
from asyncviz.stress.workload_generators.topology_workload import (
    generate_topology_storm,
)


async def run_topology_explosion_storm(context: ScenarioContext) -> None:
    cfg = context.config
    nodes = generate_topology_storm(
        node_count=cfg.topology_node_explosion,
        seed=context.rng.seed,
        fanout=4,
        depth=max(4, cfg.dependency_depth),
    )
    seen: dict[str, int] = {}
    for node in nodes:
        seen[node.node_id] = node.depth
        context.record_signal(
            "operation",
            f"topology-add:{node.node_id}",
        )
    # Verify roots have no parents (graph invariant — caught by the
    # validator if the workload generator drifts).
    roots = [n for n in nodes if n.depth == 0]
    for root in roots:
        if root.parent_ids:
            context.record_signal("failure", "root-has-parent")
    context.record_signal(
        "custom",
        f"topology-size={len(seen)}",
        float(len(seen)),
    )
