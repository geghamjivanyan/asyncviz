"""Backpressure policy — state → degradation actions.

The :class:`OverloadDetector` emits state transitions; the policy
turns each transition into a sequence of
:class:`DegradationAction` records that downstream subsystems
react to.

Default policy:

* ``NORMAL``     → emit a ``release`` action so subsystems that
  applied tighter sampling can return to baseline.
* ``ELEVATED``   → ``tighten-sampling``.
* ``OVERLOAD``   → ``tighten-sampling`` + ``engage-websocket-shedding``
  + ``drain-low-priority-queue``.
* ``EMERGENCY``  → all of the above + the configured
  ``emergency_action`` (``shed`` / ``disconnect`` / ``halt``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
)
from asyncviz.runtime.backpressure.models.degradation_action import (
    ActionKind,
    DegradationAction,
)
from asyncviz.runtime.backpressure.models.overload_state import OverloadState


@runtime_checkable
class BackpressurePolicy(Protocol):
    """Tiny contract — one method that maps state to actions."""

    def actions_for(
        self,
        *,
        previous: OverloadState,
        next_state: OverloadState,
    ) -> Sequence[DegradationAction]: ...


@dataclass(slots=True)
class DefaultBackpressurePolicy:
    """Standard pressure → action mapping."""

    config: BackpressureConfig

    def actions_for(
        self,
        *,
        previous: OverloadState,
        next_state: OverloadState,
    ) -> Sequence[DegradationAction]:
        # No state change → no actions.
        if previous == next_state:
            return ()

        if next_state == OverloadState.NORMAL:
            return (
                DegradationAction(
                    kind="release",
                    detail=f"pressure cleared (was={previous.name})",
                ),
            )

        if next_state == OverloadState.ELEVATED:
            return (
                DegradationAction(
                    kind="tighten-sampling",
                    detail="pressure elevated",
                    target_subsystem="sampler",
                ),
            )

        if next_state == OverloadState.OVERLOAD:
            return (
                DegradationAction(
                    kind="tighten-sampling",
                    detail="pressure overload",
                    target_subsystem="sampler",
                ),
                DegradationAction(
                    kind="engage-websocket-shedding",
                    detail="pressure overload",
                    target_subsystem="websocket",
                ),
                DegradationAction(
                    kind="drain-low-priority-queue",
                    detail="pressure overload",
                    target_subsystem="bus",
                ),
                DegradationAction(
                    kind="flush-recorder",
                    detail="pressure overload",
                    target_subsystem="recorder",
                ),
            )

        # EMERGENCY
        emergency = self._emergency_action()
        return (
            DegradationAction(
                kind="tighten-sampling",
                detail="emergency-mode entered",
                target_subsystem="sampler",
            ),
            DegradationAction(
                kind="engage-websocket-shedding",
                detail="emergency-mode entered",
                target_subsystem="websocket",
            ),
            DegradationAction(
                kind="drain-low-priority-queue",
                detail="emergency-mode entered",
                target_subsystem="bus",
            ),
            DegradationAction(
                kind="flush-recorder",
                detail="emergency-mode entered",
                target_subsystem="recorder",
            ),
            emergency,
        )

    def _emergency_action(self) -> DegradationAction:
        kind: ActionKind = "tighten-sampling"
        detail = "emergency action: shed"
        if self.config.emergency_action == "disconnect":
            kind = "disconnect-slow-clients"
            detail = "emergency action: disconnect"
        elif self.config.emergency_action == "halt":
            kind = "halt-production"
            detail = "emergency action: halt"
        return DegradationAction(
            kind=kind,
            detail=detail,
            target_subsystem="*",
        )
