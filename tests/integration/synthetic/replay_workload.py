"""Synthetic replay-frame stream generator."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from asyncviz.stress.utils.deterministic_rng import (  # type: ignore[import-not-found]
    DeterministicRng,
)


@dataclass(frozen=True, slots=True)
class SyntheticReplayFrame:
    sequence: int
    time_seconds: float
    keyframe: bool
    payload_kind: str


def generate_replay_stream(
    *,
    frames: int,
    seed: int,
    keyframe_period: int = 64,
    base_dt_s: float = 0.005,
) -> Iterator[SyntheticReplayFrame]:
    """Deterministic replay frame stream.

    Identical seeds + identical frame counts produce identical
    sequences — this is the foundation of the determinism check.
    """
    if frames < 0:
        raise ValueError(f"frames must be >= 0 (got {frames})")
    if keyframe_period < 1:
        raise ValueError(f"keyframe_period must be >= 1 (got {keyframe_period})")
    rng = DeterministicRng(seed)
    t = 0.0
    for index in range(frames):
        dt = max(0.0, rng.jitter(base_dt_s, 0.5))
        t += dt
        keyframe = index % keyframe_period == 0
        payload_kind = "keyframe" if keyframe else "delta"
        yield SyntheticReplayFrame(
            sequence=index,
            time_seconds=t,
            keyframe=keyframe,
            payload_kind=payload_kind,
        )
