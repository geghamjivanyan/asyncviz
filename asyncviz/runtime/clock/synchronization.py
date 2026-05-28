"""Placeholder for distributed-clock synchronization primitives.

The local :class:`RuntimeClock` is authoritative for a single process. When
AsyncViz observes multiple runtimes (multi-process, multi-host), each will
publish its own ``runtime_id`` + clock anchor and a coordinator will need to
estimate the relative skew between them.

This module reserves the public surface so consumers can import the symbols
today; the actual implementation lands when multi-runtime aggregation does.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClockSkewSample:
    """One probe of the offset between two runtime clocks.

    ``offset_ns`` is ``remote - local`` measured at the moment of the probe.
    Positive means the remote clock is ahead of the local one.
    """

    local_runtime_id: uuid.UUID
    remote_runtime_id: uuid.UUID
    local_monotonic_ns: int
    remote_monotonic_ns: int
    offset_ns: int

    @property
    def offset_seconds(self) -> float:
        return self.offset_ns / 1_000_000_000


@dataclass(frozen=True, slots=True)
class ClockSkewEstimate:
    """Aggregated skew across multiple samples — reserved for v2 multi-runtime."""

    remote_runtime_id: uuid.UUID
    samples: int
    mean_offset_ns: int
    stddev_ns: int


def estimate_skew(_samples: list[ClockSkewSample]) -> ClockSkewEstimate | None:
    """Reserved entry point for future skew estimation.

    Returns ``None`` until the multi-runtime aggregation layer is built.
    Kept here so the import path is stable across releases.
    """
    return None
