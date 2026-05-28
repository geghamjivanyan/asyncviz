"""Deterministic synthetic workloads for integration scenarios.

Re-exports the stress-layer generators so the integration framework
shares one source of synthetic data. New integration-specific
generators land in this package.
"""

from asyncviz.stress.workload_generators import (  # type: ignore[import-not-found]
    SyntheticEvent,
    SyntheticTaskDescriptor,
    TopologyNode,
    generate_event_storm,
    generate_payload_storm,
    generate_task_storm,
    generate_topology_storm,
    stable_payload,
)
from tests.integration.synthetic.render_workload import (
    SyntheticRenderTick,
    generate_render_stream,
)
from tests.integration.synthetic.replay_workload import (
    SyntheticReplayFrame,
    generate_replay_stream,
)

__all__ = [
    "SyntheticEvent",
    "SyntheticRenderTick",
    "SyntheticReplayFrame",
    "SyntheticTaskDescriptor",
    "TopologyNode",
    "generate_event_storm",
    "generate_payload_storm",
    "generate_render_stream",
    "generate_replay_stream",
    "generate_task_storm",
    "generate_topology_storm",
    "stable_payload",
]
