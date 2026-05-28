"""Scheduler-cadence compatibility bridge.

Observes ``call_soon`` / ``call_later`` / ``call_at`` cadence by
wrapping the loop methods. The bridge never *changes* what the
loop does — it counts + records anomalies. An anomaly is a callback
scheduled for the past (``call_at`` with a time before the current
``loop.time()``), which usually indicates clock drift between the
loop's monotonic source and ``time.monotonic()``.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SchedulerBridgeStats:
    call_soon_count: int
    call_later_count: int
    call_at_count: int
    past_due_scheduled: int
    installed: bool


class LoopSchedulerBridge:
    """Observability shim for the loop's scheduling primitives."""

    __slots__ = (
        "_call_at_count",
        "_call_later_count",
        "_call_soon_count",
        "_installed",
        "_lock",
        "_loop_ref",
        "_originals",
        "_past_due_scheduled",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._installed = False
        self._loop_ref: asyncio.AbstractEventLoop | None = None
        self._originals: dict[str, Callable[..., Any]] = {}
        self._call_soon_count = 0
        self._call_later_count = 0
        self._call_at_count = 0
        self._past_due_scheduled = 0

    def install(self, loop: asyncio.AbstractEventLoop) -> bool:
        if self._installed:
            return True
        if not hasattr(loop, "call_soon"):
            return False
        with self._lock:
            self._loop_ref = loop
            self._originals = {
                "call_soon": loop.call_soon,
                "call_later": loop.call_later,
                "call_at": loop.call_at,
            }
            loop.call_soon = self._wrapped_call_soon  # type: ignore[method-assign]
            loop.call_later = self._wrapped_call_later  # type: ignore[method-assign]
            loop.call_at = self._wrapped_call_at  # type: ignore[method-assign]
            self._installed = True
        return True

    def restore(self) -> bool:
        if not self._installed or self._loop_ref is None:
            return False
        with self._lock:
            loop = self._loop_ref
            for name, original in self._originals.items():
                with contextlib.suppress(Exception):
                    setattr(loop, name, original)
            self._installed = False
            self._originals = {}
        return True

    def stats(self) -> SchedulerBridgeStats:
        with self._lock:
            return SchedulerBridgeStats(
                call_soon_count=self._call_soon_count,
                call_later_count=self._call_later_count,
                call_at_count=self._call_at_count,
                past_due_scheduled=self._past_due_scheduled,
                installed=self._installed,
            )

    def reset(self) -> None:
        with self._lock:
            self._call_soon_count = 0
            self._call_later_count = 0
            self._call_at_count = 0
            self._past_due_scheduled = 0

    # ── internals ────────────────────────────────────────────────

    def _wrapped_call_soon(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            self._call_soon_count += 1
        return self._originals["call_soon"](callback, *args, **kwargs)

    def _wrapped_call_later(
        self,
        delay: float,
        callback: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        with self._lock:
            self._call_later_count += 1
            if delay < 0:
                self._past_due_scheduled += 1
        return self._originals["call_later"](delay, callback, *args, **kwargs)

    def _wrapped_call_at(
        self,
        when: float,
        callback: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        with self._lock:
            self._call_at_count += 1
            loop = self._loop_ref
            if loop is not None and when < loop.time():
                self._past_due_scheduled += 1
        return self._originals["call_at"](when, callback, *args, **kwargs)
