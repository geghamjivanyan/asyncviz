"""Pressure-signal models.

A :class:`PressureSignal` is one observation of pressure from a
named source — queue depth, event rate, websocket lag, anything
numeric and monotonic-ish. The detector merges signals from
multiple sources into a single smoothed value.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

PressureSource = Callable[[], int]
"""Callable returning the current pressure reading. Higher = more
pressure."""


@dataclass(frozen=True, slots=True)
class PressureSignal:
    """One reading of pressure from a named source."""

    source: str
    value: int
    capacity: int = 0
    """When > 0, the detector normalizes ``value`` to ``value/capacity``
    before merging — used by per-channel signals where the
    pressure is "queue depth out of capacity"."""

    captured_at_ns: int = field(default_factory=time.monotonic_ns)

    @property
    def ratio(self) -> float:
        if self.capacity <= 0:
            return 0.0
        if self.value <= 0:
            return 0.0
        return float(self.value) / float(self.capacity)
