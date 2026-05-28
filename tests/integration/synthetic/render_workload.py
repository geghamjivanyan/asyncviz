"""Synthetic render-frame workload."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from asyncviz.stress.utils.deterministic_rng import (  # type: ignore[import-not-found]
    DeterministicRng,
)


@dataclass(frozen=True, slots=True)
class SyntheticRenderTick:
    frame_index: int
    invalidation_count: int
    cost_ms: float
    drop: bool


def generate_render_stream(
    *,
    frames: int,
    seed: int,
    base_cost_ms: float = 6.0,
    soft_budget_ms: float = 16.0,
    drop_probability: float = 0.0,
) -> Iterator[SyntheticRenderTick]:
    if frames < 0:
        raise ValueError(f"frames must be >= 0 (got {frames})")
    rng = DeterministicRng(seed)
    for index in range(frames):
        cost = max(0.0, rng.jitter(base_cost_ms, 0.5))
        drop = rng.coin(drop_probability) or cost > soft_budget_ms
        invalidations = rng.integer(1, 16)
        yield SyntheticRenderTick(
            frame_index=index,
            invalidation_count=invalidations,
            cost_ms=cost,
            drop=drop,
        )
