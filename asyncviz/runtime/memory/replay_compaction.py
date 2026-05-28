"""Replay compaction adapter — metrics + tracing wrappers around
the layout helpers."""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock

from asyncviz.replay.format import ReplayFrame
from asyncviz.runtime.memory.event_interning import StringInterner
from asyncviz.runtime.memory.memory_observability import get_memory_metrics
from asyncviz.runtime.memory.memory_tracing import record_memory_trace
from asyncviz.runtime.memory.models.compact_frame import CompactReplayFrame
from asyncviz.runtime.memory.replay_memory_layout import (
    compact_replay_frame,
)


def compact_frame(
    frame: ReplayFrame,
    *,
    interner: StringInterner,
    intern_payload: bool = True,
) -> CompactReplayFrame:
    compact = compact_replay_frame(
        frame, interner=interner, intern_payload=intern_payload,
    )
    get_memory_metrics().record_compact_frame()
    record_memory_trace(
        "compact-frame-built",
        f"type={compact.payload_type} seq={compact.sequence}",
    )
    return compact


class ReplayFrameCache:
    """Bounded LRU cache for compact frames keyed by sequence.

    Used by replay UIs / inspectors that re-fetch the same frames
    rapidly (scrub-back-and-forth)."""

    __slots__ = ("_buf", "_capacity", "_lock")

    def __init__(self, capacity: int = 32) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._buf: OrderedDict[int, CompactReplayFrame] = OrderedDict()
        self._lock = Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    def get(self, sequence: int) -> CompactReplayFrame | None:
        with self._lock:
            value = self._buf.get(sequence)
            if value is None:
                get_memory_metrics().record_replay_cache_miss()
                return None
            self._buf.move_to_end(sequence)
            get_memory_metrics().record_replay_cache_hit()
            return value

    def put(self, frame: CompactReplayFrame) -> None:
        with self._lock:
            if frame.sequence in self._buf:
                self._buf.move_to_end(frame.sequence)
                self._buf[frame.sequence] = frame
                return
            self._buf[frame.sequence] = frame
            while len(self._buf) > self._capacity:
                evicted_seq, _ = self._buf.popitem(last=False)
                get_memory_metrics().record_replay_cache_eviction()
                record_memory_trace(
                    "replay-cache-evicted", f"seq={evicted_seq}",
                )

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()
