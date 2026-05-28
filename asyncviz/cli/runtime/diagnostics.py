"""Structured diagnostics for the CLI runtime.

A tiny ring-buffer + dataclass pair so the diagnostics endpoint /
``asyncviz doctor`` can show "what the last run command did" without
each command growing its own logging surface.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

CliLifecycleEvent = Literal[
    "parse-start",
    "parse-success",
    "parse-failure",
    "config-validated",
    "subprocess-spawn",
    "subprocess-ready",
    "subprocess-exit",
    "shutdown-signal",
    "shutdown-escalation",
    "browser-launched",
    "browser-skipped",
]


@dataclass(frozen=True, slots=True)
class CliRuntimeDiagnostics:
    """One CLI event entry."""

    event: CliLifecycleEvent
    detail: str
    at_monotonic: float = field(default_factory=time.monotonic)


_RING_CAPACITY = 128
_ring: deque[CliRuntimeDiagnostics] = deque(maxlen=_RING_CAPACITY)


def record_lifecycle_event(event: CliLifecycleEvent, detail: str = "") -> None:
    """Append one lifecycle event to the diagnostics ring."""
    _ring.append(CliRuntimeDiagnostics(event=event, detail=detail))


def get_lifecycle_events() -> tuple[CliRuntimeDiagnostics, ...]:
    """Return a snapshot of every recorded event."""
    return tuple(_ring)


def reset_lifecycle_events() -> None:
    """Clear the ring — used between tests."""
    _ring.clear()
