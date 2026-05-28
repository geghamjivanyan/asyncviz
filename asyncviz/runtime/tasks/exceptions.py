from __future__ import annotations

from asyncviz.runtime.events.models.enums import TaskState


class TaskRegistryError(Exception):
    """Base class for every task-registry failure."""


class DuplicateTaskError(TaskRegistryError):
    """Raised when a task_id is registered twice."""


class UnknownTaskError(TaskRegistryError, KeyError):
    """Raised when the registry has no record of the requested task_id."""

    def __init__(self, task_id: str) -> None:
        super().__init__(task_id)
        self.task_id = task_id


class InvalidStateTransitionError(TaskRegistryError):
    """Raised when a transition is not allowed by :data:`TRANSITIONS`."""

    def __init__(self, task_id: str, current: TaskState, target: TaskState) -> None:
        super().__init__(
            f"task {task_id!r}: cannot transition {current.value!r} -> {target.value!r}"
        )
        self.task_id = task_id
        self.current = current
        self.target = target


class InvalidParentReferenceError(TaskRegistryError):
    """Raised when ``parent_task_id`` doesn't resolve to a known task."""
