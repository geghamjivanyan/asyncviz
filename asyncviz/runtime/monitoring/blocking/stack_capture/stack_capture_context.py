"""Re-entry guard + task-metadata enrichment.

Two responsibilities:

* **Re-entry guard**: prevents the capture engine from triggering itself.
  If a frame walk somehow causes a path that re-enters the engine —
  via a logger emitting a synchronous error that the bus routes back to
  the detector, for example — we'd loop forever. A per-thread
  re-entry flag breaks the cycle cheaply.

* **Task enrichment**: derives :class:`CapturedTaskMetadata` from the
  active asyncio task. Done at capture time so the metadata reflects
  the task running *at the moment of the freeze*, not later.

Both pieces live together because they're the only stateful glue
between the engine and the rest of the runtime.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager

from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedTaskMetadata,
)


class ReentryGuard:
    """Per-thread "are we currently capturing?" flag.

    Implemented as :class:`threading.local` so calls from different
    threads don't block each other. Recursive entry on the same thread
    is the failure mode we care about — a re-entry returns
    ``allowed=False`` and the engine records a recursion suppression
    counter.
    """

    __slots__ = ("_local",)

    def __init__(self) -> None:
        self._local = threading.local()

    def in_capture(self) -> bool:
        return bool(getattr(self._local, "active", False))

    @contextmanager
    def acquire(self):
        if getattr(self._local, "active", False):
            yield False
            return
        self._local.active = True
        try:
            yield True
        finally:
            self._local.active = False


class TaskMetadataResolver:
    """Derive :class:`CapturedTaskMetadata` for the running asyncio task.

    Optionally enriched from a :class:`TaskRegistry` (passed in) so the
    captured metadata includes the lineage info the dashboard already
    tracks for tasks.

    All methods catch any exception and fall back to empty metadata —
    capture must never raise even when the task registry is in a weird
    state mid-shutdown.
    """

    __slots__ = ("_registry",)

    def __init__(self, registry=None) -> None:
        self._registry = registry

    def resolve(self) -> CapturedTaskMetadata:
        task = self._current_task_safe()
        if task is None:
            return CapturedTaskMetadata()
        try:
            task_id = str(id(task))
            task_name = task.get_name() if hasattr(task, "get_name") else None
            coro = getattr(task, "get_coro", lambda: None)()
            coroutine_name = self._coroutine_name(coro)
        except Exception:
            return CapturedTaskMetadata()
        parent_id, root_id = self._lookup_lineage(task_id)
        return CapturedTaskMetadata(
            task_id=task_id,
            task_name=task_name,
            coroutine_name=coroutine_name,
            parent_task_id=parent_id,
            root_task_id=root_id,
        )

    @staticmethod
    def _current_task_safe():
        """``asyncio.current_task()`` outside a loop raises — catch + return None."""
        try:
            return asyncio.current_task()
        except RuntimeError:
            return None
        except Exception:
            return None

    @staticmethod
    def _coroutine_name(coro) -> str | None:
        if coro is None:
            return None
        # Coroutines, async generators, and async-iter coroutines all
        # have a ``__qualname__`` attribute on their code object via
        # ``cr_code`` / ``ag_code``. Use the most informative thing
        # available.
        for attr in ("cr_code", "ag_code", "gi_code"):
            code = getattr(coro, attr, None)
            if code is not None:
                qualname = getattr(code, "co_qualname", None)
                if isinstance(qualname, str):
                    return qualname
                return getattr(code, "co_name", None)
        return getattr(coro, "__qualname__", None) or getattr(coro, "__name__", None)

    def _lookup_lineage(self, task_id: str) -> tuple[str | None, str | None]:
        if self._registry is None:
            return None, None
        try:
            record = self._registry.get(task_id)
        except Exception:
            return None, None
        if record is None:
            return None, None
        parent = getattr(record, "parent_task_id", None)
        root = getattr(record, "root_task_id", None)
        return parent, root
