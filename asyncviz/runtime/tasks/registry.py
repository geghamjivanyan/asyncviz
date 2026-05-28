from __future__ import annotations

import threading
import time
from typing import Any

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.events.models.task import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskResumedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
)
from asyncviz.runtime.lineage import (
    CyclicAncestryError,
    LineageMetricsSnapshot,
    LineageTracker,
    TaskLineage,
)
from asyncviz.runtime.tasks.exceptions import (
    DuplicateTaskError,
    InvalidParentReferenceError,
    InvalidStateTransitionError,
    UnknownTaskError,
)
from asyncviz.runtime.tasks.indexing import TaskIndex
from asyncviz.runtime.tasks.metrics import RegistryMetrics, RegistryMetricsSnapshot
from asyncviz.runtime.tasks.models import RuntimeTask, TaskMetadata, TaskSnapshot
from asyncviz.runtime.tasks.snapshots import snapshot_tasks
from asyncviz.runtime.tasks.state import (
    TERMINAL_STATES,
    can_transition,
    is_terminal,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.tasks.registry")


class TaskRegistry:
    """Authoritative in-memory view of every observed asyncio task.

    Thread-safe — instrumentation publishing from a user-owned loop and
    dashboard handlers running on the embedded uvicorn loop share the
    registry through a single re-entrant lock. Critical sections are kept
    small so contention stays low at thousands of updates per second.

    The registry exposes three layers:

    * ``register`` / ``update_state`` / ``remove`` — the write API. Always
      validated. Invalid input raises a :class:`TaskRegistryError` subclass.
    * ``get`` / ``list`` — the read API. Returns live :class:`RuntimeTask`
      objects; treat them as read-only.
    * ``snapshot_*`` — the export API. Returns immutable, JSON-safe
      :class:`TaskSnapshot` tuples ready to ship over the websocket.
    """

    def __init__(self, *, lineage: LineageTracker | None = None) -> None:
        self._lock = threading.RLock()
        self._index = TaskIndex()
        self._metrics = RegistryMetrics()
        self._lineage = lineage or LineageTracker()

    @property
    def lineage(self) -> LineageTracker:
        return self._lineage

    # ── lifecycle ─────────────────────────────────────────────────────────
    async def start(self) -> None:
        """Lifecycle hook for the dashboard lifespan.

        Currently a no-op; reserved so future background sweepers (e.g.
        TTL-based purging of completed tasks) can plug in without touching
        the public API.
        """

    async def stop(self) -> None:
        """Symmetric counterpart to :meth:`start`. Clears the registry."""
        self.clear()

    # ── write API ────────────────────────────────────────────────────────
    def register(
        self,
        task_id: str,
        *,
        metadata: TaskMetadata | None = None,
        state: TaskState = TaskState.CREATED,
    ) -> RuntimeTask:
        with self._lock:
            if task_id in self._index.by_id:
                raise DuplicateTaskError(task_id)
            md = metadata or TaskMetadata()
            if md.parent_task_id is not None and md.parent_task_id not in self._index.by_id:
                raise InvalidParentReferenceError(
                    f"parent {md.parent_task_id!r} of {task_id!r} is not registered"
                )
            task = RuntimeTask.create(task_id, metadata=md, state=state)
            try:
                lineage = self._lineage.register(task_id, md.parent_task_id)
            except CyclicAncestryError:
                # Refuse the parent linkage but keep the task — same fallback
                # we use for unresolved parents on replay.
                lineage = self._lineage.register(task_id, None)
                task.parent_task_id = None
            self._apply_lineage(task, lineage)
            if md.parent_task_id is not None:
                self._refresh_parent_child_count(md.parent_task_id)
            self._index.add(task)
            self._metrics.task_registered(task.state)
            logger.debug("registered task %s (state=%s)", task_id, state)
            return task

    def update_state(
        self,
        task_id: str,
        target: TaskState,
        *,
        completed_at: float | None = None,
        duration_seconds: float | None = None,
        exception_type: str | None = None,
        exception_message: str | None = None,
        cancellation_origin: str | None = None,
        metadata_update: dict[str, Any] | None = None,
        tags_update: dict[str, str] | None = None,
    ) -> RuntimeTask:
        with self._lock:
            task = self._index.by_id.get(task_id)
            if task is None:
                raise UnknownTaskError(task_id)
            if not can_transition(task.state, target):
                raise InvalidStateTransitionError(task_id, task.state, target)

            old_state = task.state
            self._index.move_state(task, old_state, target)
            task.state = target
            task.updated_at = time.time()

            if duration_seconds is not None:
                task.duration_seconds = duration_seconds
            if exception_type is not None:
                task.exception_type = exception_type
            if exception_message is not None:
                task.exception_message = exception_message
            if cancellation_origin is not None:
                task.cancellation_origin = cancellation_origin
            if metadata_update:
                task.metadata.update(metadata_update)
            if tags_update:
                task.tags.update(tags_update)
            if is_terminal(target):
                task.completed_at = completed_at if completed_at is not None else time.time()
                if task.duration_seconds is not None:
                    self._metrics.record_duration(target, task.duration_seconds)
                if target == TaskState.CANCELLED:
                    self._metrics.record_cancellation_origin(task.cancellation_origin)

            self._metrics.task_transitioned(old_state, target)
            return task

    def remove(self, task_id: str) -> bool:
        with self._lock:
            task = self._index.by_id.get(task_id)
            if task is None:
                return False
            self._index.remove(task)
            self._lineage.unregister(task_id)
            parent_id = task.parent_task_id
            if parent_id is not None and parent_id in self._index.by_id:
                self._refresh_parent_child_count(parent_id)
            self._metrics.task_removed(task.state)
            return True

    def clear(self) -> None:
        with self._lock:
            self._index.clear()
            self._lineage.clear()
            self._metrics = RegistryMetrics()

    # ── read API ─────────────────────────────────────────────────────────
    def get(self, task_id: str) -> RuntimeTask | None:
        with self._lock:
            return self._index.by_id.get(task_id)

    def get_by_asyncio_id(self, asyncio_task_id: int) -> RuntimeTask | None:
        with self._lock:
            mapped = self._index.by_asyncio_id.get(asyncio_task_id)
            return self._index.by_id.get(mapped) if mapped is not None else None

    def list(
        self,
        *,
        state: TaskState | None = None,
        parent_task_id: str | None = "__unset__",
    ) -> list[RuntimeTask]:
        with self._lock:
            return list(self._index.filter(state=state, parent_task_id=parent_task_id))

    def children_of(self, parent_task_id: str | None) -> list[RuntimeTask]:
        with self._lock:
            return list(self._index.filter(parent_task_id=parent_task_id))

    # ── lineage queries ──────────────────────────────────────────────────
    def get_children(self, task_id: str) -> list[RuntimeTask]:
        """Direct children of ``task_id``, in deterministic order."""
        with self._lock:
            return [
                self._index.by_id[child]
                for child in self._lineage.children(task_id)
                if child in self._index.by_id
            ]

    def get_descendants(self, task_id: str) -> list[RuntimeTask]:
        """All descendants of ``task_id`` (BFS order, ``task_id`` excluded)."""
        with self._lock:
            return [
                self._index.by_id[node]
                for node in self._lineage.descendants(task_id)
                if node in self._index.by_id
            ]

    def get_root_tasks(self) -> list[RuntimeTask]:
        """Tasks with no parent. Includes orphans whose parent was unregistered."""
        with self._lock:
            return [
                self._index.by_id[tid]
                for tid in self._lineage.list_roots()
                if tid in self._index.by_id
            ]

    def lineage_of(self, task_id: str) -> TaskLineage | None:
        return self._lineage.lineage_of(task_id)

    def list_cancellations_by_origin(self, origin: str | None) -> list[RuntimeTask]:
        """Return cancelled tasks whose ``cancellation_origin`` matches.

        Pass ``None`` to list cancellations with no recorded origin.
        """
        with self._lock:
            ids = self._index.by_state.get(TaskState.CANCELLED, set())
            return [
                self._index.by_id[tid]
                for tid in ids
                if tid in self._index.by_id and self._index.by_id[tid].cancellation_origin == origin
            ]

    def __len__(self) -> int:
        with self._lock:
            return len(self._index)

    def __contains__(self, task_id: object) -> bool:
        if not isinstance(task_id, str):
            return False
        with self._lock:
            return task_id in self._index.by_id

    # ── snapshots ────────────────────────────────────────────────────────
    def snapshot_active_tasks(self) -> tuple[TaskSnapshot, ...]:
        with self._lock:
            active = (
                task for task in self._index.by_id.values() if task.state not in TERMINAL_STATES
            )
            return snapshot_tasks(active)

    def snapshot_all_tasks(self) -> tuple[TaskSnapshot, ...]:
        with self._lock:
            return snapshot_tasks(self._index.by_id.values())

    def snapshot_task(self, task_id: str) -> TaskSnapshot | None:
        with self._lock:
            task = self._index.by_id.get(task_id)
            return TaskSnapshot.from_task(task) if task is not None else None

    # ── metrics ──────────────────────────────────────────────────────────
    def metrics_snapshot(self) -> RegistryMetricsSnapshot:
        with self._lock:
            return self._metrics.snapshot()

    def lineage_metrics_snapshot(self) -> LineageMetricsSnapshot:
        return self._lineage.metrics_snapshot()

    # ── event bus extension point ────────────────────────────────────────
    def handle_event(self, event: object) -> None:
        """Apply a typed task event to the registry.

        Intended to be wired up via ``bus.subscribe(registry.handle_event,
        event_types={EventType.TASK_*})``. Not auto-subscribed — the
        bootstrap layer owns the connection so the registry stays usable
        without an event bus (tests, replay, scripted populations).
        """
        if isinstance(event, TaskCreatedEvent):
            self._handle_created(event)
        elif isinstance(event, TaskStartedEvent):
            self._safe_update(event.task_id, TaskState.RUNNING)
        elif isinstance(event, TaskWaitingEvent):
            self._safe_update(event.task_id, TaskState.WAITING)
        elif isinstance(event, TaskResumedEvent):
            self._safe_update(event.task_id, TaskState.RUNNING)
        elif isinstance(event, TaskCompletedEvent):
            self._safe_update(
                event.task_id,
                TaskState.COMPLETED,
                duration_seconds=event.duration_seconds,
            )
        elif isinstance(event, TaskCancelledEvent):
            self._safe_update(
                event.task_id,
                TaskState.CANCELLED,
                duration_seconds=event.duration_seconds,
                cancellation_origin=event.cancellation_origin,
            )
        elif isinstance(event, TaskFailedEvent):
            self._safe_update(
                event.task_id,
                TaskState.FAILED,
                duration_seconds=event.duration_seconds,
                exception_type=event.exception_type,
                exception_message=event.exception_message,
            )

    def _handle_created(self, event: TaskCreatedEvent) -> None:
        if event.task_id in self:
            return  # idempotent — duplicates from replay or noisy producers are safe
        try:
            self.register(
                event.task_id,
                metadata=TaskMetadata(
                    coroutine_name=event.coroutine_name,
                    task_name=event.task_name,
                    parent_task_id=event.parent_task_id,
                    runtime_id=event.runtime_id,
                    extra=dict(event.metadata),
                ),
            )
        except InvalidParentReferenceError:
            # Drop the parent linkage rather than the whole event — parent may
            # arrive later in replay scenarios. Logged at debug for trace.
            logger.debug(
                "unresolved parent %r for %r; registering without parent",
                event.parent_task_id,
                event.task_id,
            )
            self.register(
                event.task_id,
                metadata=TaskMetadata(
                    coroutine_name=event.coroutine_name,
                    task_name=event.task_name,
                    parent_task_id=None,
                    runtime_id=event.runtime_id,
                    extra=dict(event.metadata),
                ),
            )

    def _safe_update(
        self,
        task_id: str,
        target: TaskState,
        **kwargs: Any,
    ) -> None:
        try:
            self.update_state(task_id, target, **kwargs)
        except UnknownTaskError:
            logger.debug("update_state on unknown task %r → ignored", task_id)
        except InvalidStateTransitionError as exc:
            # Duplicate terminal events land here. We record the rejection
            # so it's observable in metrics, but the registry stays consistent.
            with self._lock:
                self._metrics.record_rejected_transition()
            logger.debug("invalid transition for %r: %s", task_id, exc)

    # ── lineage helpers (private) ────────────────────────────────────────
    def _apply_lineage(self, task: RuntimeTask, lineage: TaskLineage) -> None:
        """Mirror the tracker's computed lineage onto the task record."""
        task.root_task_id = lineage.root_task_id
        task.depth = lineage.depth
        task.ancestor_chain = lineage.ancestor_chain
        task.child_count = lineage.child_count

    def _refresh_parent_child_count(self, parent_task_id: str) -> None:
        """Re-stamp ``child_count`` on the parent after add/remove."""
        parent_task = self._index.by_id.get(parent_task_id)
        if parent_task is None:
            return
        parent_task.child_count = self._lineage.child_count(parent_task_id)
