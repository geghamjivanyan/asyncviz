"""Process-wide registry of instrumented semaphores.

Pattern mirrors :mod:`asyncviz.instrumentation.queue.queue_registry`:

* keyed by ``id(semaphore)`` for cheap O(1) lookup
* values hold a ``weakref`` so the registry never extends a
  semaphore's lifetime
* a per-entry finalizer prunes the map when the semaphore is GC'd
* the registry is thread-safe via a :class:`threading.Lock`
"""

from __future__ import annotations

import itertools
import threading
import time
import weakref
from collections.abc import Iterator
from dataclasses import dataclass

from asyncviz.instrumentation.semaphore.semaphore_metadata import (
    SemaphoreIdentity,
    SemaphoreKind,
)
from asyncviz.instrumentation.semaphore.semaphore_state import (
    classify_semaphore,
    read_bound_value,
)


@dataclass(slots=True)
class _RegistryEntry:
    identity: SemaphoreIdentity
    ref: weakref.ReferenceType


class SemaphoreRegistry:
    """Thread-safe weakref-based semaphore registry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._by_object: dict[int, _RegistryEntry] = {}
        self._finalized = 0

    # ── registration ──────────────────────────────────────────────

    def register(
        self,
        semaphore: object,
        *,
        initial_value: int,
        creator_task_id: str | None,
        name: str | None = None,
    ) -> SemaphoreIdentity:
        """Register ``semaphore`` + return its identity. Idempotent."""
        obj_id = id(semaphore)
        with self._lock:
            entry = self._by_object.get(obj_id)
            if entry is not None and entry.ref() is semaphore:
                return entry.identity
            sid = f"s-{next(self._counter)}"
            kind: SemaphoreKind = classify_semaphore(semaphore)
            bound = read_bound_value(semaphore, initial_value)
            identity = SemaphoreIdentity(
                semaphore_id=sid,
                object_id=obj_id,
                semaphore_kind=kind,
                initial_value=initial_value,
                bound_value=bound,
                created_at_ns=time.monotonic_ns(),
                creator_task_id=creator_task_id,
                name=name,
            )
            ref = weakref.ref(semaphore, self._make_finalizer(obj_id))
            self._by_object[obj_id] = _RegistryEntry(identity=identity, ref=ref)
            return identity

    def _make_finalizer(self, obj_id: int):  # type: ignore[no-untyped-def]
        def _finalize(_ref: object) -> None:
            with self._lock:
                if self._by_object.pop(obj_id, None) is not None:
                    self._finalized += 1

        return _finalize

    # ── lookups ───────────────────────────────────────────────────

    def get(self, semaphore: object) -> SemaphoreIdentity | None:
        with self._lock:
            entry = self._by_object.get(id(semaphore))
            if entry is None:
                return None
            if entry.ref() is not semaphore:
                return None
            return entry.identity

    def get_by_id(self, semaphore_id: str) -> SemaphoreIdentity | None:
        with self._lock:
            for entry in self._by_object.values():
                if entry.identity.semaphore_id == semaphore_id:
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

    def iter_identities(self) -> Iterator[SemaphoreIdentity]:
        with self._lock:
            for entry in list(self._by_object.values()):
                yield entry.identity


_default_registry = SemaphoreRegistry()


def get_default_semaphore_registry() -> SemaphoreRegistry:
    return _default_registry


def reset_default_semaphore_registry() -> None:
    _default_registry.reset()
