"""Cursor runtime — atomic holder for :class:`SeekCursor`."""

from __future__ import annotations

import threading

from asyncviz.replay.runtime.seek.models.seek_cursor import SeekCursor


class SeekCursorRuntime:
    """Mutable cursor holder with atomic swap semantics."""

    __slots__ = ("_cursor", "_lock")

    def __init__(self, initial: SeekCursor | None = None) -> None:
        self._lock = threading.Lock()
        self._cursor = initial or SeekCursor.at_start()

    @property
    def cursor(self) -> SeekCursor:
        with self._lock:
            return self._cursor

    def set(self, cursor: SeekCursor) -> None:
        with self._lock:
            self._cursor = cursor

    def reset(self) -> None:
        with self._lock:
            self._cursor = SeekCursor.at_start()
