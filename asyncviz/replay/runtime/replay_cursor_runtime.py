"""Engine-side cursor coordination.

A thin object that owns the current :class:`EngineCursor` behind
a lock so the playback loop, the seek runtime, and external
introspection (``engine.cursor``) all see the same value without
racing."""

from __future__ import annotations

import threading

from asyncviz.replay.runtime.models.engine_cursor import EngineCursor


class CursorRuntime:
    """Mutable cursor holder with atomic swap semantics."""

    __slots__ = ("_cursor", "_lock")

    def __init__(self, initial: EngineCursor | None = None) -> None:
        self._lock = threading.Lock()
        self._cursor = initial or EngineCursor.at_start()

    @property
    def cursor(self) -> EngineCursor:
        with self._lock:
            return self._cursor

    def set(self, cursor: EngineCursor) -> None:
        with self._lock:
            self._cursor = cursor

    def reset(self) -> None:
        with self._lock:
            self._cursor = EngineCursor.at_start()
