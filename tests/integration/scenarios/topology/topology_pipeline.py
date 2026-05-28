"""Topology growth integration scenario."""

from __future__ import annotations

from tests.integration.harness.scenario_context import IntegrationContext
from tests.integration.synthetic import generate_topology_storm


async def run_topology_pipeline(context: IntegrationContext) -> None:
    nodes = generate_topology_storm(
        node_count=context.config.task_count,
        seed=context.rng.seed,
        fanout=4,
        depth=8,
    )
    for node in nodes:
        context.record(
            "operation",
            f"topology:{node.node_id}:depth={node.depth}",
        )
    roots = [n for n in nodes if n.depth == 0]
    if any(node.parent_ids for node in roots):
        context.record("failure", "root-has-parent")
    context.record(
        "custom",
        f"node-count={len(nodes)}",
        value=float(len(nodes)),
    )
