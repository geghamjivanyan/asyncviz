"""Websocket-side backpressure adapter.

Per-subscriber bounded channel + slow-client isolation. When a
subscriber's queue depth crosses the configured high-water mark,
the adapter flips into "slow client" state: subsequent low-priority
events are dropped, the controller is notified, and (under
emergency-mode) the client can be disconnected.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
    DropPolicy,
)
from asyncviz.runtime.backpressure.bounded_event_channel import (
    BoundedEventChannel,
    ChannelStats,
)
from asyncviz.runtime.backpressure.models.overflow_marker import OverflowMarker


@dataclass(frozen=True, slots=True)
class SubscriberStats:
    subscriber_id: str
    channel: ChannelStats
    slow_client: bool
    disconnect_count: int
    last_disconnect_ns: int = 0


class WebsocketSubscriberChannel:
    """One subscriber's bounded outbound channel + slow-client flag."""

    __slots__ = (
        "_channel",
        "_disconnect_count",
        "_last_disconnect_ns",
        "_lock",
        "_slow_client",
        "_subscriber_id",
    )

    def __init__(
        self,
        subscriber_id: str,
        *,
        capacity: int,
        policy: DropPolicy = "drop-oldest",
    ) -> None:
        self._subscriber_id = subscriber_id
        self._channel: BoundedEventChannel = BoundedEventChannel(
            f"ws:{subscriber_id}",
            capacity=capacity,
            policy=policy,
        )
        self._slow_client = False
        self._disconnect_count = 0
        self._last_disconnect_ns = 0
        self._lock = threading.Lock()

    @property
    def subscriber_id(self) -> str:
        return self._subscriber_id

    @property
    def channel(self) -> BoundedEventChannel:
        return self._channel

    @property
    def slow_client(self) -> bool:
        with self._lock:
            return self._slow_client

    def offer(self, frame, *, priority: int = 0):  # type: ignore[no-untyped-def]
        return self._channel.offer(frame, priority=priority)

    def take(self):  # type: ignore[no-untyped-def]
        return self._channel.take()

    def mark_slow(self) -> None:
        with self._lock:
            self._slow_client = True

    def mark_recovered(self) -> None:
        with self._lock:
            self._slow_client = False

    def disconnect(self) -> None:
        with self._lock:
            self._disconnect_count += 1
            self._last_disconnect_ns = time.monotonic_ns()
            self._channel.clear()
            self._slow_client = False

    def stats(self) -> SubscriberStats:
        with self._lock:
            return SubscriberStats(
                subscriber_id=self._subscriber_id,
                channel=self._channel.stats(),
                slow_client=self._slow_client,
                disconnect_count=self._disconnect_count,
                last_disconnect_ns=self._last_disconnect_ns,
            )


class WebsocketBackpressureRegistry:
    """Registry of per-subscriber channels."""

    __slots__ = ("_capacity", "_channels", "_config", "_lock", "_policy")

    def __init__(
        self,
        config: BackpressureConfig,
        *,
        policy: DropPolicy | None = None,
    ) -> None:
        self._config = config
        self._capacity = config.websocket_capacity
        self._policy = policy or config.websocket_drop_policy
        self._channels: dict[str, WebsocketSubscriberChannel] = {}
        self._lock = threading.RLock()

    def attach(self, subscriber_id: str) -> WebsocketSubscriberChannel:
        with self._lock:
            channel = self._channels.get(subscriber_id)
            if channel is None:
                channel = WebsocketSubscriberChannel(
                    subscriber_id,
                    capacity=self._capacity,
                    policy=self._policy,
                )
                self._channels[subscriber_id] = channel
            return channel

    def detach(self, subscriber_id: str) -> None:
        with self._lock:
            self._channels.pop(subscriber_id, None)

    def get(self, subscriber_id: str) -> WebsocketSubscriberChannel | None:
        with self._lock:
            return self._channels.get(subscriber_id)

    def all(self) -> tuple[WebsocketSubscriberChannel, ...]:
        with self._lock:
            return tuple(self._channels.values())

    def disconnect_slow_clients(self) -> int:
        """Disconnect every subscriber currently marked slow."""
        disconnected = 0
        with self._lock:
            channels = tuple(self._channels.values())
        for channel in channels:
            if channel.slow_client:
                channel.disconnect()
                disconnected += 1
        return disconnected

    def max_pressure_ratio(self) -> float:
        with self._lock:
            channels = tuple(self._channels.values())
        if not channels:
            return 0.0
        return max(ch.channel.pressure_ratio for ch in channels)

    def reset(self) -> None:
        with self._lock:
            self._channels.clear()


def overflow_marker_for_subscriber(
    subscriber_id: str,
    *,
    first_sequence: int,
    last_sequence: int,
    dropped: int,
    drop_policy: str,
    state_at_overflow: str,
) -> OverflowMarker:
    return OverflowMarker(
        first_sequence=first_sequence,
        last_sequence=last_sequence,
        dropped=dropped,
        subsystem=f"websocket:{subscriber_id}",
        drop_policy=drop_policy,
        state_at_overflow=state_at_overflow,
    )


_FactoryToken = Callable[[], int]  # placeholder for future hooks
