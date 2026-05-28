"""Subsystem identifier enum.

Coarse buckets the resilience manager understands. Operators that
need finer granularity register custom subsystem names; the manager
treats unknown names the same as ``CUSTOM``.
"""

from __future__ import annotations

from enum import StrEnum


class SubsystemId(StrEnum):
    REPLAY = "replay"
    WEBSOCKET = "websocket"
    REDUCER = "reducer"
    RENDER = "render"
    RECORDER = "recorder"
    INSTRUMENTATION = "instrumentation"
    """Bucket for the asyncio-task instrumentation layer."""

    CUSTOM = "custom"
    """Catch-all for operator-registered subsystems."""


CRITICAL_SUBSYSTEMS: frozenset[SubsystemId] = frozenset(
    {
        SubsystemId.REPLAY,
        SubsystemId.RECORDER,
    },
)
"""Subsystems whose collapse triggers ``emergency`` mode by default."""
