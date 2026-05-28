"""Degradation actions emitted by the controller.

When the overload state changes, the policy emits one or more
:class:`DegradationAction` records describing what downstream
should do. Subsystems subscribe + react.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ActionKind = Literal[
    "tighten-sampling",
    "engage-websocket-shedding",
    "drain-low-priority-queue",
    "disconnect-slow-clients",
    "flush-recorder",
    "halt-production",
    "release",
]


@dataclass(frozen=True, slots=True)
class DegradationAction:
    """One degradation directive."""

    kind: ActionKind
    detail: str = ""
    target_subsystem: str = ""
    """Optional namespace hint (``websocket``, ``recorder``, …).
    Empty string means "everyone listens"."""
