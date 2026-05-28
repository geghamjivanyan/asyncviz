"""Process-wide registry of instrumented ``asyncio.gather`` calls.

Unlike the queue + semaphore registries (keyed by the live object's
``id()``) a gather doesn't expose a stable user-visible handle. We key
by the engine-allocated ``g-N`` string and store the identity by value.
The result-future returned by the original ``asyncio.gather`` *is* the
natural anchor; we keep a ``weakref`` to it so the registry self-prunes
when the awaiter releases the future.
"""

from __future__ import annotations

import itertools
import threading
import time
import weakref
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from asyncviz.instrumentation.gather.gather_metadata import GatherIdentity


@dataclass(slots=True)
class _RegistryEntry:
    identity: GatherIdentity
    ref: weakref.ReferenceType | None
    completed_count: int = 0
    cancelled: bool = False
    failed: bool = False


class GatherRegistry:
    """Thread-safe gather registry with weakref-based auto-pruning."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._entries: dict[str, _RegistryEntry] = {}
        self._finalized = 0

    # ── registration ──────────────────────────────────────────────

    def register(
        self,
        *,
        parent_task_id: str | None,
        child_task_ids: Sequence[str],
        return_exceptions: bool,
        anchor: object | None = None,
    ) -> GatherIdentity:
        """Allocate a fresh ``g-N`` id + record the identity.

        ``anchor`` is the gather's result-future. When the awaiter drops
        the last reference, the finalizer prunes the registry entry —
        no manual cleanup needed for short-lived gathers.
        """
        with self._lock:
            gid = f"g-{next(self._counter)}"
            identity = GatherIdentity(
                gather_id=gid,
                parent_task_id=parent_task_id,
                child_task_ids=tuple(child_task_ids),
                child_count=len(child_task_ids),
                return_exceptions=return_exceptions,
                created_at_ns=time.monotonic_ns(),
            )
            ref: weakref.ReferenceType | None
            if anchor is not None:
                try:
                    ref = weakref.ref(anchor, self._make_finalizer(gid))
                except TypeError:
                    # Non-weakreffable anchor (rare — Futures are normally
                    # weakreffable). Skip the finalizer; ``forget()`` from
                    # the engine's done-callback handles cleanup instead.
                    ref = None
            else:
                ref = None
            self._entries[gid] = _RegistryEntry(identity=identity, ref=ref)
            return identity

    def _make_finalizer(self, gid: str):  # type: ignore[no-untyped-def]
        def _finalize(_ref: object) -> None:
            with self._lock:
                if self._entries.pop(gid, None) is not None:
                    self._finalized += 1
        return _finalize

    # ── updates from the engine ───────────────────────────────────

    def record_child_completed(self, gather_id: str) -> tuple[int, int] | None:
        """Bump ``completed_count``. Returns ``(completed, total)`` or
        ``None`` if the registry no longer tracks the gather (e.g. a
        cleanup race after finalization)."""
        with self._lock:
            entry = self._entries.get(gather_id)
            if entry is None:
                return None
            entry.completed_count += 1
            return entry.completed_count, entry.identity.child_count

    def mark_terminal(
        self, gather_id: str, *, cancelled: bool = False, failed: bool = False,
    ) -> None:
        with self._lock:
            entry = self._entries.get(gather_id)
            if entry is None:
                return
            if cancelled:
                entry.cancelled = True
            if failed:
                entry.failed = True

    def forget(self, gather_id: str) -> None:
        """Explicit removal — paired with the engine's ``gather_completed``
        callback so the registry doesn't outlive interest in the gather
        even when the weakref finalizer is unavailable."""
        with self._lock:
            if self._entries.pop(gather_id, None) is not None:
                self._finalized += 1

    # ── lookups ───────────────────────────────────────────────────

    def get(self, gather_id: str) -> GatherIdentity | None:
        with self._lock:
            entry = self._entries.get(gather_id)
            return entry.identity if entry is not None else None

    def progress(self, gather_id: str) -> tuple[int, int, bool, bool] | None:
        """Return ``(completed, total, cancelled, failed)`` or ``None``."""
        with self._lock:
            entry = self._entries.get(gather_id)
            if entry is None:
                return None
            return (
                entry.completed_count,
                entry.identity.child_count,
                entry.cancelled,
                entry.failed,
            )

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

    def iter_identities(self) -> Iterator[GatherIdentity]:
        with self._lock:
            for entry in list(self._entries.values()):
                yield entry.identity


_default_registry = GatherRegistry()


def get_default_gather_registry() -> GatherRegistry:
    return _default_registry


def reset_default_gather_registry() -> None:
    _default_registry.reset()
