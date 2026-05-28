"""Process-wide registry of instrumented queues.

The registry is the source of truth for queue identity. Lookups are
keyed by ``id(queue)`` so they're cheap; entries hold a weakref to
the underlying queue so the registry doesn't extend its lifetime.

When the queue is garbage-collected the weakref finalizer prunes the
entry — no manual cleanup is required from the patcher.
"""

from __future__ import annotations

import itertools
import threading
import time
import weakref
from collections.abc import Iterator
from dataclasses import dataclass

from asyncviz.instrumentation.queue.queue_metadata import (
    QueueIdentity,
    QueueKind,
)
from asyncviz.instrumentation.queue.queue_state import classify_queue


@dataclass(slots=True)
class _RegistryEntry:
    identity: QueueIdentity
    ref: weakref.ReferenceType


class QueueRegistry:
    """Thread-safe weakref-based queue registry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._by_object: dict[int, _RegistryEntry] = {}
        self._finalized = 0

    # ── registration ──────────────────────────────────────────────

    def register(
        self,
        queue: object,
        *,
        creator_task_id: str | None,
        name: str | None = None,
    ) -> QueueIdentity:
        """Register ``queue`` + return its identity. Idempotent."""
        obj_id = id(queue)
        with self._lock:
            entry = self._by_object.get(obj_id)
            if entry is not None and entry.ref() is queue:
                return entry.identity
            queue_id = f"q-{next(self._counter)}"
            kind: QueueKind = classify_queue(queue)
            try:
                maxsize = int(getattr(queue, "maxsize", 0) or 0)
            except Exception:
                maxsize = 0
            identity = QueueIdentity(
                queue_id=queue_id,
                object_id=obj_id,
                queue_kind=kind,
                maxsize=maxsize,
                created_at_ns=time.monotonic_ns(),
                creator_task_id=creator_task_id,
                name=name,
            )
            ref = weakref.ref(queue, self._make_finalizer(obj_id))
            self._by_object[obj_id] = _RegistryEntry(identity=identity, ref=ref)
            return identity

    def _make_finalizer(self, obj_id: int):  # type: ignore[no-untyped-def]
        def _finalize(_ref: object) -> None:
            with self._lock:
                if self._by_object.pop(obj_id, None) is not None:
                    self._finalized += 1
        return _finalize

    # ── lookups ───────────────────────────────────────────────────

    def get(self, queue: object) -> QueueIdentity | None:
        with self._lock:
            entry = self._by_object.get(id(queue))
            if entry is None:
                return None
            if entry.ref() is not queue:
                # Stale entry — id reuse after GC.
                return None
            return entry.identity

    def get_by_id(self, queue_id: str) -> QueueIdentity | None:
        with self._lock:
            for entry in self._by_object.values():
                if entry.identity.queue_id == queue_id:
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
        """Clear the registry. Used by tests + process teardown."""
        with self._lock:
            self._by_object.clear()
            self._counter = itertools.count(1)
            self._finalized = 0

    def iter_identities(self) -> Iterator[QueueIdentity]:
        with self._lock:
            for entry in list(self._by_object.values()):
                yield entry.identity


_default_registry = QueueRegistry()


def get_default_queue_registry() -> QueueRegistry:
    return _default_registry


def reset_default_queue_registry() -> None:
    _default_registry.reset()
