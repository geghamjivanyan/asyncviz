"""Reducer base types — :class:`ReducerContext`, :class:`ReducerResult`, :class:`Reducer`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.transitions import TransitionRecord

if TYPE_CHECKING:
    from asyncviz.runtime.state.reducers.metrics import ReducerMetrics
    from asyncviz.runtime.state.reducers.projections import ProjectionInvalidationBus
    from asyncviz.runtime.state.reducers.transitions import TransitionHistory
    from asyncviz.runtime.tasks import TaskRegistry


@dataclass(frozen=True, slots=True)
class ReducerContext:
    """Read/write surface a reducer is allowed to touch.

    Reducers MUST NOT reach outside this struct — that's how we keep them
    pure and replay-safe. The store assembles a fresh ``ReducerContext``
    per apply with the same components every time.
    """

    registry: TaskRegistry
    history: TransitionHistory
    projections: ProjectionInvalidationBus
    metrics: ReducerMetrics
    sequence: int | None


@dataclass(frozen=True, slots=True)
class ReducerResult:
    """Outcome of a reducer apply.

    ``applied`` distinguishes "the reducer mutated state" from "the reducer
    bailed out cleanly because the transition was invalid / terminal /
    stale." The store routes both into metrics but only successful applies
    notify subscribers.
    """

    applied: bool
    transition: TransitionRecord | None = None
    target_state: TaskState | None = None
    reason: str | None = None
    invalid_transition: bool = False
    terminal_blocked: bool = False

    @classmethod
    def ok(
        cls,
        *,
        transition: TransitionRecord,
        target_state: TaskState,
    ) -> ReducerResult:
        return cls(applied=True, transition=transition, target_state=target_state)

    @classmethod
    def rejected(
        cls,
        *,
        reason: str,
        invalid_transition: bool = False,
        terminal_blocked: bool = False,
    ) -> ReducerResult:
        return cls(
            applied=False,
            reason=reason,
            invalid_transition=invalid_transition,
            terminal_blocked=terminal_blocked,
        )


@runtime_checkable
class Reducer(Protocol):
    """Protocol every reducer implements.

    Implementations are stateless — context comes in, result comes out, no
    mutation outside ``ctx``. The reducer's ``event_type`` attribute is the
    runtime dispatch key.
    """

    event_type: type[RuntimeEvent]
    name: str

    def apply(self, ctx: ReducerContext, event: RuntimeEvent) -> ReducerResult:  # pragma: no cover
        ...
