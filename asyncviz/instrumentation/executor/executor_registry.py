"""Process-wide registries of instrumented executors + work items.

* :class:`ExecutorRegistry` — keyed by ``id(executor)``, weakref-anchored
  so the registry self-prunes when a custom executor is GC'd. The loop's
  default executor lives as long as the loop, so its anchor is rarely
  collected.
* :class:`WorkItemRegistry` — keyed by the engine-allocated ``w-N`` id.
  The anchor is the asyncio Future the loop returns from
  ``run_in_executor`` — finalizing once the awaiter drops it.
"""

from __future__ import annotations

import itertools
import threading
import time
import weakref
from collections.abc import Iterator
from dataclasses import dataclass

from asyncviz.instrumentation.executor.executor_metadata import (
    ExecutorIdentity,
    ExecutorKind,
    WorkItemIdentity,
)
from asyncviz.instrumentation.executor.executor_state import (
    classify_executor,
    read_max_workers,
    read_thread_name_prefix,
)


@dataclass(slots=True)
class _ExecutorEntry:
    identity: ExecutorIdentity
    ref: weakref.ReferenceType | None


class ExecutorRegistry:
    """Thread-safe registry of instrumented executors."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._by_object: dict[int, _ExecutorEntry] = {}
        self._finalized = 0

    def register(
        self,
        executor: object,
        *,
        is_default: bool,
        creator_task_id: str | None,
        name: str | None = None,
    ) -> ExecutorIdentity:
        """Register ``executor`` + return its identity. Idempotent.

        Use :meth:`register_or_get` when callers need to know whether
        the identity was freshly allocated (so they can emit
        ``executor.registered`` exactly once per executor).
        """
        identity, _ = self.register_or_get(
            executor,
            is_default=is_default,
            creator_task_id=creator_task_id,
            name=name,
        )
        return identity

    def register_or_get(
        self,
        executor: object,
        *,
        is_default: bool,
        creator_task_id: str | None,
        name: str | None = None,
    ) -> tuple[ExecutorIdentity, bool]:
        """Return ``(identity, is_new)`` — ``is_new`` is ``True`` only on
        the first registration of an executor object."""
        obj_id = id(executor)
        with self._lock:
            entry = self._by_object.get(obj_id)
            if entry is not None and (entry.ref is None or entry.ref() is executor):
                return entry.identity, False
            eid = f"e-{next(self._counter)}"
            kind: ExecutorKind = classify_executor(executor, is_default=is_default)
            identity = ExecutorIdentity(
                executor_id=eid,
                object_id=obj_id,
                executor_kind=kind,
                max_workers=read_max_workers(executor),
                thread_name_prefix=read_thread_name_prefix(executor),
                created_at_ns=time.monotonic_ns(),
                creator_task_id=creator_task_id,
                name=name,
            )
            ref: weakref.ReferenceType | None
            try:
                ref = weakref.ref(executor, self._make_finalizer(obj_id))
            except TypeError:
                ref = None
            self._by_object[obj_id] = _ExecutorEntry(identity=identity, ref=ref)
            return identity, True

    def _make_finalizer(self, obj_id: int):  # type: ignore[no-untyped-def]
        def _finalize(_ref: object) -> None:
            with self._lock:
                if self._by_object.pop(obj_id, None) is not None:
                    self._finalized += 1

        return _finalize

    def get(self, executor: object) -> ExecutorIdentity | None:
        with self._lock:
            entry = self._by_object.get(id(executor))
            if entry is None:
                return None
            if entry.ref is not None and entry.ref() is not executor:
                return None
            return entry.identity

    def get_by_id(self, executor_id: str) -> ExecutorIdentity | None:
        with self._lock:
            for entry in self._by_object.values():
                if entry.identity.executor_id == executor_id:
                    return entry.identity
            return None

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_object)

    @property
    def finalized_count(self) -> int:
        with self._lock:
            return self._finalized

    def reset(self) -> None:
        with self._lock:
            self._by_object.clear()
            self._counter = itertools.count(1)
            self._finalized = 0

    def iter_identities(self) -> Iterator[ExecutorIdentity]:
        with self._lock:
            for entry in list(self._by_object.values()):
                yield entry.identity


# ── work-item registry ────────────────────────────────────────────────


@dataclass(slots=True)
class _WorkItemEntry:
    identity: WorkItemIdentity
    started: bool = False
    completed: bool = False
    cancelled: bool = False
    failed: bool = False
    started_at_ns: int | None = None
    finished_at_ns: int | None = None
    worker_thread_name: str | None = None
    exception_type: str | None = None


class WorkItemRegistry:
    """Thread-safe registry of in-flight work items."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._entries: dict[str, _WorkItemEntry] = {}
        self._finalized = 0

    def register(
        self,
        *,
        executor_id: str,
        submitting_task_id: str | None,
        callable_name: str | None,
    ) -> WorkItemIdentity:
        with self._lock:
            wid = f"w-{next(self._counter)}"
            identity = WorkItemIdentity(
                work_item_id=wid,
                executor_id=executor_id,
                submitting_task_id=submitting_task_id,
                submitted_at_ns=time.monotonic_ns(),
                callable_name=callable_name,
            )
            self._entries[wid] = _WorkItemEntry(identity=identity)
            return identity

    def mark_started(
        self,
        work_item_id: str,
        *,
        worker_thread_name: str | None,
        started_at_ns: int,
    ) -> None:
        with self._lock:
            entry = self._entries.get(work_item_id)
            if entry is None:
                return
            entry.started = True
            entry.started_at_ns = started_at_ns
            entry.worker_thread_name = worker_thread_name

    def mark_completed(self, work_item_id: str, *, finished_at_ns: int) -> None:
        with self._lock:
            entry = self._entries.get(work_item_id)
            if entry is None:
                return
            entry.completed = True
            entry.finished_at_ns = finished_at_ns

    def mark_failed(
        self,
        work_item_id: str,
        *,
        finished_at_ns: int,
        exception_type: str | None,
    ) -> None:
        with self._lock:
            entry = self._entries.get(work_item_id)
            if entry is None:
                return
            entry.failed = True
            entry.finished_at_ns = finished_at_ns
            entry.exception_type = exception_type

    def mark_cancelled(self, work_item_id: str, *, finished_at_ns: int) -> None:
        with self._lock:
            entry = self._entries.get(work_item_id)
            if entry is None:
                return
            entry.cancelled = True
            entry.finished_at_ns = finished_at_ns

    def get(self, work_item_id: str) -> WorkItemIdentity | None:
        with self._lock:
            entry = self._entries.get(work_item_id)
            return entry.identity if entry is not None else None

    def state(self, work_item_id: str) -> _WorkItemEntry | None:
        with self._lock:
            return self._entries.get(work_item_id)

    def forget(self, work_item_id: str) -> None:
        with self._lock:
            if self._entries.pop(work_item_id, None) is not None:
                self._finalized += 1

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def finalized_count(self) -> int:
        with self._lock:
            return self._finalized

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()
            self._counter = itertools.count(1)
            self._finalized = 0

    def iter_identities(self) -> Iterator[WorkItemIdentity]:
        with self._lock:
            for entry in list(self._entries.values()):
                yield entry.identity


_default_executor_registry = ExecutorRegistry()
_default_work_item_registry = WorkItemRegistry()


def get_default_executor_registry() -> ExecutorRegistry:
    return _default_executor_registry


def reset_default_executor_registry() -> None:
    _default_executor_registry.reset()


def get_default_work_item_registry() -> WorkItemRegistry:
    return _default_work_item_registry


def reset_default_work_item_registry() -> None:
    _default_work_item_registry.reset()
