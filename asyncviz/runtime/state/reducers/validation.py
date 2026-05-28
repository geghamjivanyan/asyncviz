"""Lifecycle transition validation.

Wraps :mod:`asyncviz.runtime.tasks.state` with reducer-specific semantics:

* the ``CREATED → CREATED`` no-op (duplicate creation) is treated as
  invalid here even though :func:`can_transition` returns False for it;
* the ``terminal → anything`` case is broken out as
  :class:`TerminalStateLockedError` so the metrics layer can split
  "stale terminal" from generic invalid transitions.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.exceptions import (
    InvalidTransitionError,
    TerminalStateLockedError,
)
from asyncviz.runtime.tasks.state import TERMINAL_STATES, can_transition, is_terminal


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    """Resolved decision produced by :func:`evaluate_transition`.

    Carries everything the reducer needs to act:

    * ``allowed`` — proceed with the registry mutation;
    * ``current`` / ``target`` — explicit endpoints (caller doesn't have to
      look them up again);
    * ``reason`` — populated only when ``allowed`` is False, surfaced to
      metrics + debug logs.
    """

    allowed: bool
    current: TaskState | None
    target: TaskState
    reason: str | None = None
    terminal_blocked: bool = False


def evaluate_transition(
    current: TaskState | None,
    target: TaskState,
) -> TransitionPlan:
    """Decide whether ``current → target`` is acceptable.

    ``current=None`` means the task isn't tracked yet — only ``CREATED`` is
    allowed as the first transition. Everything else returns ``allowed=False``
    and the caller (registry / reducer) should drop the event as stale.
    """
    if current is None:
        if target is TaskState.CREATED:
            return TransitionPlan(allowed=True, current=None, target=target)
        return TransitionPlan(
            allowed=False,
            current=None,
            target=target,
            reason=f"unknown task; first event must be CREATED, got {target.value!r}",
        )

    if target is TaskState.CREATED:
        # Re-creation of an already-tracked task is always rejected — the
        # registry's idempotent path handles duplicates upstream.
        return TransitionPlan(
            allowed=False,
            current=current,
            target=target,
            reason=f"task already tracked in state {current.value!r}",
        )

    if is_terminal(current):
        return TransitionPlan(
            allowed=False,
            current=current,
            target=target,
            reason=f"task already terminal in state {current.value!r}",
            terminal_blocked=True,
        )

    if not can_transition(current, target):
        return TransitionPlan(
            allowed=False,
            current=current,
            target=target,
            reason=f"no transition from {current.value!r} → {target.value!r}",
        )

    return TransitionPlan(allowed=True, current=current, target=target)


def assert_transition(current: TaskState | None, target: TaskState) -> None:
    """Strict variant — raise instead of returning a verdict.

    Tests and replay-validation tools use this; reducers themselves call
    :func:`evaluate_transition` and route via the plan.
    """
    plan = evaluate_transition(current, target)
    if plan.allowed:
        return
    if plan.terminal_blocked:
        raise TerminalStateLockedError(plan.reason or "terminal state locked")
    raise InvalidTransitionError(plan.reason or "invalid transition")


def list_terminal_states() -> frozenset[TaskState]:
    return TERMINAL_STATES
