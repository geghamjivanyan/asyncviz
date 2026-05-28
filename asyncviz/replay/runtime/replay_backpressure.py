"""Dispatch-queue backpressure for the replay engine.

The engine itself runs pull-based, but its outbound paths
(websocket bridge, async sinks) can stall. The dispatch queue is
soft-capped — once the depth crosses ``capacity``, the engine
records a backpressure event and the producer (the playback loop)
either blocks on a semaphore or yields control until the sink
catches up.

We keep this module light: one async ``Semaphore``-style guard +
an overflow guard counter for diagnostics."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Final

DEFAULT_DISPATCH_QUEUE_CAPACITY: Final[int] = 4096


class DispatchOverflowError(RuntimeError):
    """Raised when the dispatch queue would exceed its hard cap."""


@dataclass(slots=True)
class DispatchGate:
    """Async-friendly counter-based gate.

    The engine calls :meth:`acquire` before pushing onto an outbound
    channel and :meth:`release` after the sink drains it. Acquire
    yields control if the depth would exceed ``capacity``, so the
    engine loop naturally backpressures."""

    capacity: int = DEFAULT_DISPATCH_QUEUE_CAPACITY
    _semaphore: asyncio.Semaphore | None = None

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError("capacity must be >= 1")
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.capacity)

    @property
    def depth(self) -> int:
        if self._semaphore is None:
            return 0
        # Best-effort introspection — Semaphore doesn't expose a
        # public depth, so we infer from its private ``_value``.
        value = getattr(self._semaphore, "_value", self.capacity)
        return self.capacity - int(value)

    @property
    def at_capacity(self) -> bool:
        return self.depth >= self.capacity

    async def acquire(self) -> None:
        assert self._semaphore is not None
        await self._semaphore.acquire()

    def release(self) -> None:
        assert self._semaphore is not None
        self._semaphore.release()


@dataclass(slots=True)
class OverflowSampler:
    """Time-windowed overflow event aggregator (similar shape to
    the format-layer ``OverflowGuard``)."""

    window_seconds: float = 1.0
    threshold: int = 16
    _window_start: float = 0.0
    _count: int = 0

    def trip(self) -> bool:
        now = time.monotonic()
        if now - self._window_start > self.window_seconds:
            self._window_start = now
            self._count = 0
        self._count += 1
        return self._count >= self.threshold

    def reset(self) -> None:
        self._window_start = 0.0
        self._count = 0
