from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.tasks.models import RuntimeTask


class TaskIndex:
    """Multi-key index over the registry's task records.

    Kept inside the registry — never exposed across the lock boundary. All
    operations assume the caller holds the registry's lock; the index itself
    is unsynchronized.
    """

    def __init__(self) -> None:
        self.by_id: dict[str, RuntimeTask] = {}
        self.by_asyncio_id: dict[int, str] = {}
        self.by_state: dict[TaskState, set[str]] = defaultdict(set)
        self.by_parent: dict[str | None, set[str]] = defaultdict(set)

    def add(self, task: RuntimeTask) -> None:
        self.by_id[task.task_id] = task
        if task.asyncio_task_id is not None:
            self.by_asyncio_id[task.asyncio_task_id] = task.task_id
        self.by_state[task.state].add(task.task_id)
        self.by_parent[task.parent_task_id].add(task.task_id)

    def remove(self, task: RuntimeTask) -> None:
        self.by_id.pop(task.task_id, None)
        if task.asyncio_task_id is not None:
            self.by_asyncio_id.pop(task.asyncio_task_id, None)
        bucket = self.by_state.get(task.state)
        if bucket is not None:
            bucket.discard(task.task_id)
            if not bucket:
                self.by_state.pop(task.state, None)
        parent_bucket = self.by_parent.get(task.parent_task_id)
        if parent_bucket is not None:
            parent_bucket.discard(task.task_id)
            if not parent_bucket:
                self.by_parent.pop(task.parent_task_id, None)

    def move_state(self, task: RuntimeTask, old: TaskState, new: TaskState) -> None:
        if old == new:
            return
        old_bucket = self.by_state.get(old)
        if old_bucket is not None:
            old_bucket.discard(task.task_id)
            if not old_bucket:
                self.by_state.pop(old, None)
        self.by_state[new].add(task.task_id)

    def filter(
        self,
        *,
        state: TaskState | None = None,
        parent_task_id: str | None = "__unset__",
    ) -> Iterable[RuntimeTask]:
        if state is not None and parent_task_id != "__unset__":
            ids = self.by_state.get(state, set()) & self.by_parent.get(parent_task_id, set())
        elif state is not None:
            ids = self.by_state.get(state, set())
        elif parent_task_id != "__unset__":
            ids = self.by_parent.get(parent_task_id, set())
        else:
            ids = set(self.by_id)
        return (self.by_id[i] for i in ids if i in self.by_id)

    def clear(self) -> None:
        self.by_id.clear()
        self.by_asyncio_id.clear()
        self.by_state.clear()
        self.by_parent.clear()

    def __len__(self) -> int:
        return len(self.by_id)
