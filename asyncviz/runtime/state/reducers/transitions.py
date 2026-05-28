"""Per-task transition history.

Reducers append a :class:`TransitionRecord` here on every successful apply.
The history is the substrate for the future timeline panel: it preserves
the (state, sequence, monotonic_ns) triple needed to plot run / wait
segments without re-walking the event log.

Bounded per-task to keep memory predictable under long-running tasks that
ping-pong between RUNNING and WAITING.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from asyncviz.runtime.events.models.enums import TaskState

#: Per-task transition cap. 1024 transitions = ~512 run/wait flip-flops which
#: is well past any practical asyncio workload before the ring rolls.
DEFAULT_HISTORY_LIMIT: int = 1024


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    """One step in a task's lifecycle.

    Field order is the wire order — coordinate with the TypeScript
    ``TransitionRecord`` definition.
    """

    sequence: int | None
    state: TaskState
    monotonic_ns: int
    wall_seconds: float
    event_id: str
    event_type: str

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "state": self.state.value,
            "monotonic_ns": self.monotonic_ns,
            "wall_seconds": self.wall_seconds,
            "event_id": self.event_id,
            "event_type": self.event_type,
        }


class TransitionHistory:
    """Bounded ring of :class:`TransitionRecord`\\ s per task.

    Thread-safe. The reducer registry appends here from the store's apply
    path; snapshot builders read here from the snapshot path. Both sides
    hold the registry's lock externally, but the history's own lock
    isolates concurrent reads (e.g. an HTTP request hitting a specific
    task's history while a reducer is appending elsewhere).
    """

    def __init__(self, *, per_task_limit: int = DEFAULT_HISTORY_LIMIT) -> None:
        if per_task_limit < 1:
            raise ValueError("per_task_limit must be >= 1")
        self._lock = threading.RLock()
        self._limit = per_task_limit
        self._records: dict[str, deque[TransitionRecord]] = {}
        self._evicted = 0
        self._appended = 0

    @property
    def per_task_limit(self) -> int:
        return self._limit

    @property
    def total_appended(self) -> int:
        with self._lock:
            return self._appended

    @property
    def total_evicted(self) -> int:
        with self._lock:
            return self._evicted

    def append(self, task_id: str, record: TransitionRecord) -> None:
        with self._lock:
            bucket = self._records.get(task_id)
            if bucket is None:
                bucket = deque(maxlen=self._limit)
                self._records[task_id] = bucket
            if len(bucket) == self._limit:
                self._evicted += 1
            bucket.append(record)
            self._appended += 1

    def get(self, task_id: str) -> tuple[TransitionRecord, ...]:
        with self._lock:
            bucket = self._records.get(task_id)
            return tuple(bucket) if bucket is not None else ()

    def discard(self, task_id: str) -> None:
        with self._lock:
            self._records.pop(task_id, None)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._evicted = 0
            self._appended = 0

    def __contains__(self, task_id: object) -> bool:
        if not isinstance(task_id, str):
            return False
        with self._lock:
            return task_id in self._records

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def task_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._records.keys())

    def export(self) -> dict[str, list[dict[str, object]]]:
        """JSON-safe snapshot of every task's history."""
        with self._lock:
            return {
                task_id: [record.as_dict() for record in bucket]
                for task_id, bucket in self._records.items()
            }

    def iter_records(self, task_id: str) -> Iterator[TransitionRecord]:
        # Snapshot-then-iterate so the lock doesn't span user code.
        yield from self.get(task_id)

    def append_many(self, task_id: str, records: Iterable[TransitionRecord]) -> None:
        """Used by replay rebuild paths to seed history without going through reducers."""
        for record in records:
            self.append(task_id, record)
