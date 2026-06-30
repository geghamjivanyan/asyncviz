"""Adaptive backpressure controller.

Wraps the :class:`OverloadDetector` + :class:`BackpressurePolicy`
into one ``tick()``-driven loop the runtime owner calls
periodically (e.g. once per 100ms). Each tick:

1. Samples every registered pressure source.
2. Feeds the samples to the detector.
3. If the state changed, runs the policy + fans actions out to
   subscribers.

Designed to be sync-friendly so it can be driven from either the
event loop or a periodic ``threading.Timer`` thread.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
)
from asyncviz.runtime.backpressure.backpressure_policy import (
    BackpressurePolicy,
    DefaultBackpressurePolicy,
)
from asyncviz.runtime.backpressure.models.degradation_action import (
    DegradationAction,
)
from asyncviz.runtime.backpressure.models.overload_state import (
    OverloadSnapshot,
    OverloadState,
)
from asyncviz.runtime.backpressure.models.pressure_signal import (
    PressureSignal,
    PressureSource,
)
from asyncviz.runtime.backpressure.overload_detector import OverloadDetector

ActionListener = Callable[[DegradationAction, OverloadSnapshot], None]


@dataclass(slots=True)
class _SourceEntry:
    name: str
    callable_: PressureSource
    capacity: int


class AdaptiveBackpressureController:
    """Periodic sampler + action dispatcher."""

    __slots__ = (
        "_action_listeners",
        "_config",
        "_detector",
        "_lock",
        "_policy",
        "_sources",
        "_state",
    )

    def __init__(
        self,
        *,
        config: BackpressureConfig,
        detector: OverloadDetector | None = None,
        policy: BackpressurePolicy | None = None,
    ) -> None:
        self._config = config
        self._detector = detector or OverloadDetector(config)
        self._policy = policy or DefaultBackpressurePolicy(config)
        self._sources: dict[str, _SourceEntry] = {}
        self._action_listeners: list[ActionListener] = []
        self._lock = threading.RLock()
        self._state = OverloadState.NORMAL

    # ── source registration ──────────────────────────────────────

    def register_source(
        self,
        name: str,
        callable_: PressureSource,
        *,
        capacity: int = 0,
    ) -> Callable[[], None]:
        """Register a pressure-source callable. Returns an
        unsubscribe handle.

        ``capacity`` lets the detector normalize a depth into a
        ratio. Pass 0 for sources whose value is already a ratio /
        already normalized."""
        with self._lock:
            self._sources[name] = _SourceEntry(
                name=name,
                callable_=callable_,
                capacity=capacity,
            )

        def _unsubscribe() -> None:
            with self._lock:
                self._sources.pop(name, None)

        return _unsubscribe

    # ── tick ─────────────────────────────────────────────────────

    def tick(self) -> OverloadSnapshot:
        """Sample + transition + dispatch — one tick."""
        with self._lock:
            sources = tuple(self._sources.values())
        snapshot: OverloadSnapshot | None = None
        previous_state = self._detector.state
        for entry in sources:
            try:
                value = int(entry.callable_())
            except Exception:
                continue
            signal = PressureSignal(
                source=entry.name,
                value=value,
                capacity=entry.capacity,
            )
            snapshot = self._detector.observe(signal)
        if snapshot is None:
            snapshot = self._detector.snapshot()
        if snapshot.state != previous_state:
            self._dispatch_actions(previous_state, snapshot)
        self._state = snapshot.state
        return snapshot

    # ── action listeners ─────────────────────────────────────────

    def subscribe_actions(
        self,
        listener: ActionListener,
    ) -> Callable[[], None]:
        with self._lock:
            self._action_listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._action_listeners:
                    self._action_listeners.remove(listener)

        return _unsubscribe

    def _dispatch_actions(
        self,
        previous: OverloadState,
        snapshot: OverloadSnapshot,
    ) -> None:
        actions = self._policy.actions_for(
            previous=previous,
            next_state=snapshot.state,
        )
        with self._lock:
            listeners = tuple(self._action_listeners)
        for action in actions:
            for listener in listeners:
                # Isolate listener faults — one bad subscriber must
                # not break the action fan-out.
                with contextlib.suppress(Exception):
                    listener(action, snapshot)

    # ── accessors ─────────────────────────────────────────────────

    @property
    def detector(self) -> OverloadDetector:
        return self._detector

    @property
    def policy(self) -> BackpressurePolicy:
        return self._policy

    @property
    def state(self) -> OverloadState:
        return self._detector.state

    def reset(self) -> None:
        with self._lock:
            self._sources.clear()
            self._action_listeners.clear()
        self._detector.reset()
        self._state = OverloadState.NORMAL
