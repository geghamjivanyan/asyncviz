"""Bridge between the resilience manager + the backpressure layer.

When the resilience manager enters ``degraded`` / ``shed`` /
``emergency`` mode, the backpressure layer should *also* tighten —
otherwise the runtime will accept new traffic that can't possibly
succeed. The bridge translates resilience-mode transitions into
suggested backpressure actions, and vice versa: a backpressure
``emergency`` action should inform the resilience layer.

This module is decoupled from
:mod:`asyncviz.runtime.backpressure` to avoid circular imports.
The application wires the two together at startup.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.resilience.isolation_configuration import EmergencyMode


@dataclass(frozen=True, slots=True)
class BackpressureSuggestion:
    """Recommendation derived from the runtime mode."""

    runtime_mode: EmergencyMode
    suggested_drop_policy: str
    """One of the canonical :mod:`backpressure` drop policies:
    ``"drop-newest"``, ``"drop-oldest"``, ``"drop-low-priority"``,
    ``"block"``."""

    suggested_sampling_tier: str
    """``"full"`` / ``"structural"`` / ``"critical-only"``."""

    detail: str = ""


_DEFAULT_SUGGESTIONS: dict[EmergencyMode, BackpressureSuggestion] = {
    "normal": BackpressureSuggestion(
        runtime_mode="normal",
        suggested_drop_policy="drop-low-priority",
        suggested_sampling_tier="full",
    ),
    "degraded": BackpressureSuggestion(
        runtime_mode="degraded",
        suggested_drop_policy="drop-low-priority",
        suggested_sampling_tier="structural",
        detail="one subsystem on fallback",
    ),
    "shed": BackpressureSuggestion(
        runtime_mode="shed",
        suggested_drop_policy="drop-newest",
        suggested_sampling_tier="structural",
        detail="overload shedding active",
    ),
    "emergency": BackpressureSuggestion(
        runtime_mode="emergency",
        suggested_drop_policy="drop-newest",
        suggested_sampling_tier="critical-only",
        detail="critical subsystem unavailable",
    ),
    "halt": BackpressureSuggestion(
        runtime_mode="halt",
        suggested_drop_policy="block",
        suggested_sampling_tier="critical-only",
        detail="runtime halted for diagnostics",
    ),
}


SuggestionListener = Callable[[BackpressureSuggestion], None]


class IsolationBackpressureBridge:
    """Translates resilience-mode transitions to backpressure
    suggestions + notifies registered listeners."""

    __slots__ = ("_listeners", "_lock", "_mode", "_suggestion")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listeners: list[SuggestionListener] = []
        self._mode: EmergencyMode = "normal"
        self._suggestion = _DEFAULT_SUGGESTIONS["normal"]

    def current_suggestion(self) -> BackpressureSuggestion:
        with self._lock:
            return self._suggestion

    def current_mode(self) -> EmergencyMode:
        with self._lock:
            return self._mode

    def on_mode_change(self, mode: EmergencyMode) -> BackpressureSuggestion:
        suggestion = _DEFAULT_SUGGESTIONS.get(mode, _DEFAULT_SUGGESTIONS["normal"])
        with self._lock:
            if self._mode == mode:
                return suggestion
            self._mode = mode
            self._suggestion = suggestion
            listeners = tuple(self._listeners)
        for listener in listeners:
            with contextlib.suppress(Exception):
                listener(suggestion)
        return suggestion

    def subscribe(self, listener: SuggestionListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe
