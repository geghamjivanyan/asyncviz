"""Event-level deduplication.

Detects identical *consecutive* events (heartbeats, repeated
metric pushes, idempotent re-emits) within a sliding window so the
downstream consumer can decide whether to skip them.

Uses content-based hashing so semantically-equivalent events
(post-interning) collapse to the same digest. The window is
bounded — beyond ``window_size`` the oldest digest falls off.
"""

from __future__ import annotations

import hashlib
import threading
from collections import deque
from dataclasses import dataclass

from asyncviz.runtime.memory.memory_observability import get_memory_metrics
from asyncviz.runtime.memory.memory_tracing import record_memory_trace
from asyncviz.runtime.memory.models.compact_event import CompactEvent


@dataclass(frozen=True, slots=True)
class DedupDecision:
    """Decision returned by :meth:`EventDeduplicator.observe`."""

    duplicate: bool
    digest: str


class EventDeduplicator:
    """Sliding-window content-hash deduplicator."""

    __slots__ = ("_lock", "_recent_digests", "_window_size")

    def __init__(self, window_size: int = 1024) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._window_size = window_size
        self._recent_digests: deque[str] = deque(maxlen=window_size)
        self._lock = threading.Lock()

    @property
    def window_size(self) -> int:
        return self._window_size

    def observe(self, event: CompactEvent) -> DedupDecision:
        """Hash + check against the recent window."""
        digest = _digest_event(event)
        with self._lock:
            duplicate = digest in self._recent_digests
            if not duplicate:
                self._recent_digests.append(digest)
        metrics = get_memory_metrics()
        if duplicate:
            metrics.record_dedup_hit()
            record_memory_trace("dedup-hit", digest[:16])
        else:
            metrics.record_dedup_miss()
        return DedupDecision(duplicate=duplicate, digest=digest)

    def reset(self) -> None:
        with self._lock:
            self._recent_digests.clear()


def _digest_event(event: CompactEvent) -> str:
    """Stable content hash. The payload's dict-ordering is
    normalized by sorting keys before hashing."""
    hasher = hashlib.sha256()
    hasher.update(event.event_type.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(str(event.monotonic_ns).encode("ascii"))
    hasher.update(b"|")
    for key in sorted(event.payload.keys()):
        hasher.update(str(key).encode("utf-8"))
        hasher.update(b"=")
        hasher.update(repr(event.payload[key]).encode("utf-8"))
        hasher.update(b";")
    return hasher.hexdigest()
