"""Structured seek requests + results.

Requests are value objects so a future remote-control transport can
ship them over the wire. Results carry enough detail for the
diagnostics page to render a per-seek summary (latency, cache hit,
checkpoint used, frames replayed).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from asyncviz.replay.runtime.seek.replay_seek_configuration import (
    SeekStrategy,
    SeekTargetKind,
)


@dataclass(frozen=True, slots=True)
class SeekIntent:
    """How the caller expresses a seek target."""

    kind: SeekTargetKind
    """``sequence``, ``timestamp``, ``marker``, or ``relative``."""

    target_sequence: int = 0
    """Required when ``kind == "sequence"``."""

    target_monotonic_ns: int = 0
    """Required when ``kind == "timestamp"``."""

    marker_id: str = ""
    """Required when ``kind == "marker"``."""

    relative_delta: int = 0
    """Required when ``kind == "relative"`` — signed integer offset
    applied to the current cursor's sequence."""

    @staticmethod
    def to_sequence(sequence: int) -> SeekIntent:
        return SeekIntent(kind="sequence", target_sequence=sequence)

    @staticmethod
    def to_timestamp(monotonic_ns: int) -> SeekIntent:
        return SeekIntent(kind="timestamp", target_monotonic_ns=monotonic_ns)

    @staticmethod
    def to_marker(marker_id: str) -> SeekIntent:
        return SeekIntent(kind="marker", marker_id=marker_id)

    @staticmethod
    def relative(delta: int) -> SeekIntent:
        return SeekIntent(kind="relative", relative_delta=delta)


@dataclass(frozen=True, slots=True)
class SeekRequest:
    """Internal envelope wrapping a :class:`SeekIntent` with a
    coordinator-assigned id + acceptance timestamp."""

    request_id: int
    intent: SeekIntent
    strategy: SeekStrategy = "best_effort"
    reason: str = ""
    requested_at_ns: int = field(default_factory=time.monotonic_ns)


@dataclass(frozen=True, slots=True)
class SeekResult:
    """What the coordinator reports back when a seek finishes."""

    request_id: int
    """Matches the originating :class:`SeekRequest.request_id`."""

    target_sequence: int
    landed_sequence: int
    """The sequence the cursor settled on. May differ from
    ``target_sequence`` under ``best_effort`` strategy (overshoot)."""

    landed_monotonic_ns: int
    """Monotonic timestamp at the landed frame."""

    used_cache: bool
    """True when the reconstruction was served from the LRU cache."""

    used_checkpoint: bool
    """True when an in-memory checkpoint short-circuited
    reconstruction."""

    used_snapshot: bool
    """True when the loader fell back to disk-snapshot
    reconstruction."""

    frames_replayed: int
    latency_ns: int
    cancelled: bool = False
    error_detail: str = ""
