"""Synthetic task-workload generator.

Produces deterministic task descriptors a scenario can use to drive
asyncio without the runtime instrumentation noise. The descriptors
are plain values — scenarios decide whether to actually spawn the
task, just record the event, or feed the descriptor into a
benchmark.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from asyncviz.stress.utils.deterministic_rng import DeterministicRng


@dataclass(frozen=True, slots=True)
class SyntheticTaskDescriptor:
    """Identity + lifecycle metadata for a synthetic task."""

    task_id: str
    name: str
    parent_id: str | None
    depth: int
    duration_s: float
    will_fail: bool
    will_cancel: bool


def generate_task_storm(
    *,
    size: int,
    seed: int,
    dependency_depth: int = 1,
    cancel_ratio: float = 0.0,
    failure_ratio: float = 0.0,
    base_duration_s: float = 0.001,
) -> Iterator[SyntheticTaskDescriptor]:
    """Yield ``size`` deterministic task descriptors.

    Tasks are emitted in parent-first order so a consumer can build
    a dependency forest without reordering. Depth is bounded by
    ``dependency_depth`` to keep the spawn graph from going wider
    than the registered ceiling.
    """
    if size < 0:
        raise ValueError(f"size must be >= 0 (got {size})")
    if dependency_depth < 1:
        raise ValueError(f"dependency_depth must be >= 1 (got {dependency_depth})")
    rng = DeterministicRng(seed)
    parents_by_depth: list[list[str]] = [[] for _ in range(dependency_depth)]
    parents_by_depth[0].append("__ROOT__")
    for index in range(size):
        depth = index % dependency_depth
        candidates = parents_by_depth[depth - 1] if depth > 0 else [None]
        parent_id = rng.choice(candidates) if candidates else None
        task_id = f"t-{index:08d}"
        descriptor = SyntheticTaskDescriptor(
            task_id=task_id,
            name=f"synthetic_{index}",
            parent_id=parent_id if parent_id != "__ROOT__" else None,
            depth=depth,
            duration_s=rng.jitter(base_duration_s, 0.5),
            will_fail=rng.coin(failure_ratio),
            will_cancel=rng.coin(cancel_ratio),
        )
        parents_by_depth[depth].append(task_id)
        yield descriptor
