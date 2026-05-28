"""Websocket-side memory layer.

Pools ``bytearray`` scratch buffers used for JSON serialization
so the per-event hot path doesn't allocate a fresh buffer on
every frame.

The pool is sized for the typical max-message size; if a caller
needs more, the pool grows the buffer in-place (still amortized
cheaper than fresh allocations because the underlying memory
sticks around for reuse).
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from asyncviz.runtime.memory.memory_observability import get_memory_metrics
from asyncviz.runtime.memory.memory_tracing import record_memory_trace


@dataclass(frozen=True, slots=True)
class WebsocketBufferStats:
    capacity_buffers: int
    in_pool: int
    acquires: int
    hits: int
    default_bytes: int
    grow_events: int


class WebsocketBufferPool:
    """Pool of resettable ``bytearray`` serialization buffers."""

    __slots__ = (
        "_acquires",
        "_buf",
        "_capacity_buffers",
        "_default_bytes",
        "_grow_events",
        "_hits",
        "_lock",
    )

    def __init__(
        self, *, capacity_buffers: int = 16, default_bytes: int = 64 * 1024,
    ) -> None:
        if capacity_buffers < 1:
            raise ValueError("capacity_buffers must be >= 1")
        if default_bytes < 256:
            raise ValueError("default_bytes must be >= 256")
        self._capacity_buffers = capacity_buffers
        self._default_bytes = default_bytes
        self._buf: deque[bytearray] = deque()
        self._lock = threading.Lock()
        self._acquires = 0
        self._hits = 0
        self._grow_events = 0

    def acquire(self, *, min_bytes: int = 0) -> bytearray:
        """Return a cleared ``bytearray`` with at least ``min_bytes``
        underlying capacity."""
        target = max(min_bytes, self._default_bytes)
        with self._lock:
            self._acquires += 1
            if self._buf:
                buffer = self._buf.pop()
                self._hits += 1
                if len(buffer) < target:
                    self._grow_events += 1
                    buffer.extend(b"\x00" * (target - len(buffer)))
                    record_memory_trace(
                        "websocket-buffer-grown",
                        f"target_bytes={target}",
                    )
                del buffer[:]  # clear contents without releasing capacity
                hit = True
            else:
                buffer = bytearray(target)
                del buffer[:]
                hit = False
        get_memory_metrics().record_websocket_acquire(hit=hit)
        return buffer

    def release(self, buffer: bytearray) -> None:
        with self._lock:
            if len(self._buf) >= self._capacity_buffers:
                return  # let the buffer be GC'd
            del buffer[:]
            self._buf.append(buffer)

    def stats(self) -> WebsocketBufferStats:
        with self._lock:
            return WebsocketBufferStats(
                capacity_buffers=self._capacity_buffers,
                in_pool=len(self._buf),
                acquires=self._acquires,
                hits=self._hits,
                default_bytes=self._default_bytes,
                grow_events=self._grow_events,
            )

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()
            self._acquires = 0
            self._hits = 0
            self._grow_events = 0
