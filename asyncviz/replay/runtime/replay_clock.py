"""Virtual replay clock.

Maps wall time to *virtual* time so the engine can dispatch a frame
at the same relative cadence the recorder observed it, scaled by
the current playback speed and frozen during pauses.

Why a custom clock instead of an ``asyncio.sleep`` loop with delta
arithmetic at the use site: a clock anchored at known
``(wall_anchor_ns, virtual_anchor_ns, speed)`` is the *single*
source of truth for virtual time. Pause/resume, speed change, and
seek all become explicit re-anchorings — easy to reason about, easy
to test, and the engine loop never has to track drift manually.

Determinism: the clock never drifts on its own. Only wall-clock
*advance* drives virtual-time advance, and every public mutator
(``pause``, ``resume``, ``set_speed``, ``jump_to``) re-anchors
atomically so the sequence ``current_virtual_ns() → mutate →
current_virtual_ns()`` is always consistent.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

WallClockFn = Callable[[], int]
"""Pluggable wall clock — defaults to :func:`time.monotonic_ns`. A
test that wants deterministic timing supplies its own monotonic
counter."""


@dataclass(slots=True)
class ReplayClockSnapshot:
    """Read-only view of the clock's anchor + state."""

    virtual_ns: int
    speed: float
    paused: bool
    wall_anchor_ns: int
    virtual_anchor_ns: int


class ReplayClock:
    """Virtual time generator + anchor manager."""

    __slots__ = (
        "_lock",
        "_paused",
        "_paused_virtual_ns",
        "_speed",
        "_virtual_anchor_ns",
        "_wall_anchor_ns",
        "_wall_clock",
    )

    def __init__(
        self,
        *,
        initial_virtual_ns: int = 0,
        initial_speed: float = 1.0,
        wall_clock: WallClockFn | None = None,
    ) -> None:
        if initial_speed <= 0:
            raise ValueError(f"speed must be > 0 (got {initial_speed})")
        self._lock = threading.Lock()
        self._wall_clock: WallClockFn = wall_clock or time.monotonic_ns
        self._wall_anchor_ns = self._wall_clock()
        self._virtual_anchor_ns = initial_virtual_ns
        self._speed = float(initial_speed)
        self._paused = False
        self._paused_virtual_ns: int | None = None

    # ── public mutators ───────────────────────────────────────────

    def pause(self) -> None:
        with self._lock:
            if self._paused:
                return
            self._paused_virtual_ns = self._current_virtual_locked()
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            if not self._paused:
                return
            assert self._paused_virtual_ns is not None
            self._wall_anchor_ns = self._wall_clock()
            self._virtual_anchor_ns = self._paused_virtual_ns
            self._paused_virtual_ns = None
            self._paused = False

    def set_speed(self, speed: float) -> None:
        if speed <= 0:
            raise ValueError(f"speed must be > 0 (got {speed})")
        with self._lock:
            # Re-anchor so the speed change is *forward-only* — the
            # virtual time observed right before + right after the
            # change is identical.
            current = self._current_virtual_locked()
            self._wall_anchor_ns = self._wall_clock()
            self._virtual_anchor_ns = current
            self._speed = float(speed)
            if self._paused:
                self._paused_virtual_ns = current

    def jump_to(self, virtual_ns: int) -> None:
        """Re-anchor the clock at a specific virtual time. Used by
        the engine after a seek so subsequent ``current_virtual_ns``
        starts at the seek target."""
        with self._lock:
            self._wall_anchor_ns = self._wall_clock()
            self._virtual_anchor_ns = int(virtual_ns)
            if self._paused:
                self._paused_virtual_ns = self._virtual_anchor_ns

    # ── readers ───────────────────────────────────────────────────

    def current_virtual_ns(self) -> int:
        with self._lock:
            return self._current_virtual_locked()

    @property
    def speed(self) -> float:
        with self._lock:
            return self._speed

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._paused

    def snapshot(self) -> ReplayClockSnapshot:
        with self._lock:
            return ReplayClockSnapshot(
                virtual_ns=self._current_virtual_locked(),
                speed=self._speed,
                paused=self._paused,
                wall_anchor_ns=self._wall_anchor_ns,
                virtual_anchor_ns=self._virtual_anchor_ns,
            )

    # ── internals ─────────────────────────────────────────────────

    def _current_virtual_locked(self) -> int:
        if self._paused:
            assert self._paused_virtual_ns is not None
            return self._paused_virtual_ns
        elapsed = self._wall_clock() - self._wall_anchor_ns
        if elapsed < 0:
            elapsed = 0
        return self._virtual_anchor_ns + int(elapsed * self._speed)
