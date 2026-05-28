"""Reducer registry — pluggable state evolution.

A reducer takes ``(state, frame)`` and returns the next state. The
registry routes frames to the right reducer based on
:class:`ReplayFrame.payload_type` so domains can evolve
independently of each other.

Default behavior:

* Every frame goes through the ``__default__`` reducer (advance
  counters: ``last_sequence``, ``last_monotonic_ns``,
  ``frames_applied``).
* Runtime-event payloads also pass through a per-domain reducer if
  one is registered for their event_type.
* Snapshot frames are handled by the snapshot runtime separately,
  not by reducers.

This pattern matches the loader's :func:`reconstruct_state` API so
the same reducer set works for offline reconstruction and live
playback.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState

Reducer = Callable[[VirtualRuntimeState, ReplayFrame], VirtualRuntimeState]
"""``(state, frame) -> next_state``. Must be deterministic + pure."""


@dataclass(frozen=True, slots=True)
class ReducerBinding:
    """One registry entry — keyed by payload_type."""

    payload_type: str
    reducer: Reducer


class ReducerRegistry:
    """Thread-safe registry of payload_type → reducer."""

    __slots__ = ("_default", "_lock", "_reducers")

    DEFAULT_KEY = "__default__"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reducers: dict[str, Reducer] = {}
        self._default: Reducer = _advance_counters

    def set_default(self, reducer: Reducer) -> None:
        with self._lock:
            self._default = reducer

    def register(self, payload_type: str, reducer: Reducer) -> None:
        with self._lock:
            self._reducers[str(payload_type)] = reducer

    def unregister(self, payload_type: str) -> None:
        with self._lock:
            self._reducers.pop(str(payload_type), None)

    def known_types(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._reducers))

    def apply(self, state: VirtualRuntimeState, frame: ReplayFrame) -> VirtualRuntimeState:
        """Apply default counter advance + any registered reducer."""
        with self._lock:
            default = self._default
            domain_reducer = self._reducers.get(str(frame.payload_type))
        next_state = default(state, frame)
        if domain_reducer is not None:
            next_state = domain_reducer(next_state, frame)
        return next_state

    def reset(self) -> None:
        with self._lock:
            self._reducers.clear()
            self._default = _advance_counters


# ── built-in default reducer ──────────────────────────────────────


def _advance_counters(state: VirtualRuntimeState, frame: ReplayFrame) -> VirtualRuntimeState:
    """Bump counters + capture the frame's monotonic timestamp."""
    return VirtualRuntimeState(
        last_sequence=frame.sequence,
        last_monotonic_ns=frame.monotonic_ns,
        frames_applied=state.frames_applied + 1,
        domains=state.domains,
        notes=state.notes,
    )


# ── tiny helper: domain-scoped reducer factory ────────────────────


def domain_reducer(
    domain: str,
    *,
    apply: Callable[[dict, ReplayFrame], dict],
) -> Reducer:
    """Build a reducer that scopes its mutation to one domain bucket.

    ``apply(domain_state, frame)`` should be a pure function that
    returns the next per-domain dict. The wrapper takes care of
    plumbing it back into :class:`VirtualRuntimeState`.
    """

    def _reduce(state: VirtualRuntimeState, frame: ReplayFrame) -> VirtualRuntimeState:
        current = dict(state.domains.get(domain, {}))
        next_domain = apply(current, frame)
        return state.with_domain(domain, dict(next_domain))

    return _reduce
