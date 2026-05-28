"""Multi-subsystem orchestrator.

Lazily constructs the backpressure controller, resilience manager,
and loop-compat manager + wires them together. The scenarios that
need cross-subsystem coordination call ``orchestrator.bind_all()``
to install the documented integration paths:

* resilience-mode transitions translate to backpressure suggestions
  via :class:`IsolationBackpressureBridge`,
* the compat manager's drift bridge surfaces in resilience metrics
  as ``recorder``-domain failure markers when drift exceeds
  tolerance,
* a single ``reset()`` cleans every subsystem.

The orchestrator never starts a real network listener or recorder
— it operates entirely on the in-memory APIs.
"""

from __future__ import annotations

from collections.abc import Callable

from asyncviz.runtime.backpressure import (  # type: ignore[import-not-found]
    EventBackpressureController,
)
from asyncviz.runtime.compat import (  # type: ignore[import-not-found]
    LoopCompatibilityManager,
)
from asyncviz.runtime.resilience import (  # type: ignore[import-not-found]
    BackpressureSuggestion,
    EmergencyMode,
    RuntimeFailureManager,
)


class RuntimeOrchestrator:
    """Composes the resilience / backpressure / compat managers."""

    __slots__ = (
        "_backpressure",
        "_compat",
        "_resilience",
        "_suggestion_unsubs",
    )

    def __init__(self) -> None:
        self._backpressure: EventBackpressureController | None = None
        self._resilience: RuntimeFailureManager | None = None
        self._compat: LoopCompatibilityManager | None = None
        self._suggestion_unsubs: list[Callable[[], None]] = []

    def backpressure(self) -> EventBackpressureController:
        if self._backpressure is None:
            self._backpressure = EventBackpressureController()
        return self._backpressure

    def resilience(self) -> RuntimeFailureManager:
        if self._resilience is None:
            self._resilience = RuntimeFailureManager()
        return self._resilience

    def compat(self) -> LoopCompatibilityManager:
        if self._compat is None:
            self._compat = LoopCompatibilityManager()
        return self._compat

    def bind_all(self) -> None:
        """Wire every cross-subsystem integration.

        Idempotent; subsequent calls are no-ops.
        """
        resilience = self.resilience()
        suggestions_seen: list[BackpressureSuggestion] = []
        mode_observations: list[EmergencyMode] = []
        suggestion_unsub = resilience.backpressure_bridge().subscribe(
            suggestions_seen.append,
        )
        mode_unsub = resilience.subscribe_mode(mode_observations.append)
        self._suggestion_unsubs.append(suggestion_unsub)
        self._suggestion_unsubs.append(mode_unsub)

    def reset(self) -> None:
        for unsub in self._suggestion_unsubs:
            unsub()
        self._suggestion_unsubs.clear()
        if self._resilience is not None:
            self._resilience.reset()
        if self._backpressure is not None:
            self._backpressure.reset()
        if self._compat is not None:
            self._compat.reset()
