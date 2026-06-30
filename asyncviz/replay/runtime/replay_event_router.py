"""Replay event router — pub/sub for dispatched frames.

Subscribers register a callback against either the wildcard
``"*"`` topic or one specific ``payload_type``. Every dispatched
frame fans out to matching subscribers under a single lock so the
ordering observed by every subscriber matches the engine's
canonical ordering.

Subscriber exceptions are isolated — a buggy subscriber must not
crash the playback loop. They're logged at debug level so noisy
production logs don't accumulate.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from asyncviz.replay.format import ReplayFrame
from asyncviz.utils.logging import get_logger

logger = get_logger("replay.runtime.event_router")

FrameSubscriber = Callable[[ReplayFrame], None]
"""``subscriber(frame)``. Synchronous."""


WILDCARD = "*"


class ReplayEventRouter:
    """Multi-topic synchronous router."""

    __slots__ = ("_lock", "_subscribers")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[FrameSubscriber]] = {WILDCARD: []}

    def subscribe(
        self,
        payload_type: str,
        subscriber: FrameSubscriber,
    ) -> Callable[[], None]:
        """Register a subscriber for one payload type (or the
        wildcard ``"*"``). Returns an unsubscribe handle."""
        with self._lock:
            self._subscribers.setdefault(str(payload_type), []).append(subscriber)

        def _unsubscribe() -> None:
            with self._lock:
                bucket = self._subscribers.get(str(payload_type))
                if not bucket:
                    return
                if subscriber in bucket:
                    bucket.remove(subscriber)

        return _unsubscribe

    def publish(self, frame: ReplayFrame) -> None:
        """Fan a frame out to wildcard + payload-specific subscribers."""
        with self._lock:
            wildcard = tuple(self._subscribers.get(WILDCARD, ()))
            specific = tuple(
                self._subscribers.get(str(frame.payload_type), ()),
            )
        for subscriber in wildcard + specific:
            try:
                subscriber(frame)
            except Exception as exc:
                logger.debug(
                    "replay subscriber for %s raised: %s",
                    frame.payload_type,
                    exc,
                )

    def subscriber_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._subscribers.values())

    def clear(self) -> None:
        with self._lock:
            self._subscribers = {WILDCARD: []}
