"""Reducer-side reconciliation rules.

Separate from :class:`asyncviz.runtime.state.reconciliation.ReconciliationPolicy`
which sits at the store boundary (dedup + stale). This module captures the
per-reducer rules: terminal stickiness, idempotent re-creation, and the
shape of "is this even a state mutation worth recording?" decisions.

Today these helpers are thin — the reducers already use them via the
shared lifecycle module. The file exists so future per-reducer reconciliation
rules have a clear home.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.validation import evaluate_transition


@dataclass(frozen=True, slots=True)
class ReducerReconciliation:
    """Configurable knobs the lifecycle uses."""

    allow_idempotent_terminal: bool = False
    """When True, replaying a terminal event for a task already in that exact
    terminal state is treated as a no-op success rather than a rejection.
    Disabled by default — the registry's invalid-transition counter is the
    canonical observation surface.
    """


def is_no_op_terminal(current: TaskState | None, target: TaskState) -> bool:
    """``True`` iff the proposed transition is "stay in the same terminal state"."""
    if current is None:
        return False
    return current is target and current in {
        TaskState.COMPLETED,
        TaskState.CANCELLED,
        TaskState.FAILED,
    }


def is_legal_transition(current: TaskState | None, target: TaskState) -> bool:
    """Direct passthrough for callers that only need the boolean."""
    return evaluate_transition(current, target).allowed
