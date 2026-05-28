"""Projections over reconstructed seek results.

Cheap derived views the UI consumes — domain counts at the seek
target, a "what changed" summary between the previous cursor and
the seek's landing, etc. Pure functions; no engine coupling.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.seek.models.seek_request import SeekResult


@dataclass(frozen=True, slots=True)
class SeekProjection:
    """Compact view of one completed seek."""

    target_sequence: int
    landed_sequence: int
    overshoot: int
    """Positive when the landed sequence is past the target."""

    domains_present: tuple[str, ...]
    frames_replayed: int
    used_cache: bool
    used_checkpoint: bool
    used_snapshot: bool
    latency_ms: float


def project_seek(
    *, result: SeekResult, state: VirtualRuntimeState,
) -> SeekProjection:
    """Turn a :class:`SeekResult` + state into a UI-friendly
    :class:`SeekProjection`."""
    return SeekProjection(
        target_sequence=result.target_sequence,
        landed_sequence=result.landed_sequence,
        overshoot=result.landed_sequence - result.target_sequence,
        domains_present=tuple(sorted(state.domains.keys())),
        frames_replayed=result.frames_replayed,
        used_cache=result.used_cache,
        used_checkpoint=result.used_checkpoint,
        used_snapshot=result.used_snapshot,
        latency_ms=result.latency_ns / 1_000_000,
    )
