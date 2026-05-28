"""Active event-loop kind enumeration."""

from __future__ import annotations

from enum import StrEnum


class LoopKind(StrEnum):
    """Coarse identifier for the currently-installed event loop."""

    ASYNCIO = "asyncio"
    UVLOOP = "uvloop"
    ANYIO = "anyio"
    TRIO = "trio"
    """Reserved for future bridge experimentation. The compatibility
    manager never returns :data:`TRIO` today; it's enumerated so
    downstream code can opt in without an enum migration."""
    UNKNOWN = "unknown"


def loop_kind_supports_replay(kind: LoopKind) -> bool:
    """``True`` for loops the replay layer can safely target.

    Today this is only ``asyncio`` + ``uvloop``. Trio/AnyIO depend on
    their own clocks; the compatibility manager will gate the replay
    layer until their bridges land.
    """
    return kind in (LoopKind.ASYNCIO, LoopKind.UVLOOP)
