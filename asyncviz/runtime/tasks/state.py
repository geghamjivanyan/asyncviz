from __future__ import annotations

from asyncviz.runtime.events.models.enums import TaskState

#: Registry-local alias for :class:`TaskState`. The event protocol owns the
#: canonical enum; this name keeps consumer code inside ``tasks`` clean.
TaskLifecycleState = TaskState

#: Terminal states reject further transitions.
TERMINAL_STATES: frozenset[TaskState] = frozenset(
    {TaskState.COMPLETED, TaskState.CANCELLED, TaskState.FAILED}
)

#: Allowed forward transitions. Anything not listed here is invalid.
TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.CREATED: frozenset(
        {
            TaskState.RUNNING,
            TaskState.WAITING,
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        }
    ),
    TaskState.RUNNING: frozenset(
        {
            TaskState.WAITING,
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        }
    ),
    TaskState.WAITING: frozenset(
        {
            TaskState.RUNNING,
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        }
    ),
    # Terminal states have no outgoing transitions.
    TaskState.COMPLETED: frozenset(),
    TaskState.CANCELLED: frozenset(),
    TaskState.FAILED: frozenset(),
}


def is_terminal(state: TaskState) -> bool:
    return state in TERMINAL_STATES


def can_transition(current: TaskState, target: TaskState) -> bool:
    return target in TRANSITIONS.get(current, frozenset())
