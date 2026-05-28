"""Runtime stress signal — emitted by storm scenarios.

A scenario streams structured signals to the runner; the runner
aggregates them into per-scenario counters and feeds the
:class:`ScalabilityValidator`. Keeping the signal flat + frozen
makes the in-flight cost trivial.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StressSignalKind = Literal[
    "operation",
    "failure",
    "overload",
    "emergency",
    "websocket-disconnect",
    "replay-frame",
    "render-frame",
    "memory-sample",
    "custom",
]


@dataclass(frozen=True, slots=True)
class StressSignal:
    """One event observed during a stress scenario."""

    kind: StressSignalKind
    detail: str = ""
    value: float = 0.0
    """Numeric payload — used by ``memory-sample`` (bytes), latency
    samples, etc."""
