"""Bound replay iterator.

Thin wrapper around :class:`ReplayStream` that pairs an iterator
with its trailing cursor so callers can suspend / resume / inspect.
The iterator is single-use — replaying from a captured cursor is
the loader's :meth:`seek_to_sequence` job, not the iterator's."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading.replay_cursor import ReplayCursor
from asyncviz.replay.loading.replay_stream import ReplayStream


@dataclass(slots=True)
class ReplayIteratorState:
    """Final state of one iteration pass."""

    frames_yielded: int
    final_cursor: ReplayCursor


class ReplayIterator:
    """Yields frames from a :class:`ReplayStream` and tracks state."""

    __slots__ = ("_frames_yielded", "_stream")

    def __init__(self, stream: ReplayStream) -> None:
        self._stream = stream
        self._frames_yielded = 0

    @property
    def cursor(self) -> ReplayCursor:
        return self._stream.cursor

    @property
    def frames_yielded(self) -> int:
        return self._frames_yielded

    def __iter__(self) -> Iterator[ReplayFrame]:
        for frame in self._stream:
            self._frames_yielded += 1
            yield frame

    def state(self) -> ReplayIteratorState:
        return ReplayIteratorState(
            frames_yielded=self._frames_yielded,
            final_cursor=self.cursor,
        )
