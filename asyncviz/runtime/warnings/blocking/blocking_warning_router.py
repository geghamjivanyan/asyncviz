"""Multi-sink router for emitted warning events.

The emitter doesn't talk to the bus / listeners directly — it hands the
ready-to-publish event + payload to a :class:`WarningRouter` that
fans it out across any number of registered sinks.

Sinks today: the runtime event bus (synchronous publish) + an optional
listener callback. The router exists so future destinations
(distributed-alert agents, persistent log writers, syslog forwarders)
can register without touching the emitter.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.warnings.blocking.blocking_warning_payloads import (
    BlockingWarningPayload,
)

#: Bus-shaped emitter. ``True`` means the bus accepted.
EventEmitter = Callable[[RuntimeEvent], bool]

#: Listener fired for every emitted payload. Listener exceptions are
#: caught + counted by the emitter — the router only delivers.
PayloadListener = Callable[[BlockingWarningPayload], None]


@dataclass(frozen=True, slots=True)
class RouterDispatchOutcome:
    """Result of routing one event to all configured sinks.

    ``accepted`` is the bus result (``True`` means the bus accepted;
    ``False`` means the bus dropped). ``listener_errors`` counts how
    many listener callbacks raised — the router catches them so a
    misbehaving listener doesn't break dispatch to other sinks.
    """

    accepted: bool
    listener_errors: int


class WarningRouter:
    """Fan-out for warning event emission."""

    __slots__ = ("_emitter", "_listeners", "_listeners_lock", "_next_listener_id")

    def __init__(self, *, emitter: EventEmitter | None = None) -> None:
        self._emitter = emitter
        self._listeners_lock = threading.Lock()
        self._listeners: dict[int, PayloadListener] = {}
        self._next_listener_id = 0

    @property
    def has_emitter(self) -> bool:
        return self._emitter is not None

    def set_emitter(self, emitter: EventEmitter | None) -> None:
        self._emitter = emitter

    def subscribe(self, listener: PayloadListener) -> int:
        with self._listeners_lock:
            self._next_listener_id += 1
            sid = self._next_listener_id
            self._listeners[sid] = listener
        return sid

    def unsubscribe(self, subscription_id: int) -> bool:
        with self._listeners_lock:
            return self._listeners.pop(subscription_id, None) is not None

    def listener_count(self) -> int:
        with self._listeners_lock:
            return len(self._listeners)

    def dispatch(
        self,
        *,
        event: RuntimeEvent | None,
        payload: BlockingWarningPayload,
    ) -> RouterDispatchOutcome:
        """Fan out one warning. Returns the dispatch outcome.

        ``event`` may be ``None`` when the emitter is disabled / has no
        bus wired; listeners still get invoked. ``accepted`` reflects
        the bus result (or ``True`` when no bus is configured).
        """
        accepted = True
        if event is not None and self._emitter is not None:
            try:
                accepted = bool(self._emitter(event))
            except Exception:
                # Emitter exceptions are counted upstream by the engine.
                # Re-raise so the engine's metric path records it.
                raise
        listener_errors = 0
        with self._listeners_lock:
            listeners = list(self._listeners.values())
        for listener in listeners:
            try:
                listener(payload)
            except Exception:
                listener_errors += 1
        return RouterDispatchOutcome(accepted=accepted, listener_errors=listener_errors)
