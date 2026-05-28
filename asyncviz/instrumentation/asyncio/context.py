from __future__ import annotations

import asyncio
import contextlib
import threading
import weakref
from typing import Any


class TaskContext:
    """Bookkeeping for asyncio.Task → asyncviz task_id mapping.

    Stored as a :class:`weakref.WeakKeyDictionary` so the asyncio.Task object
    is never artificially kept alive by AsyncViz. We never mutate the task
    object itself; the mapping is the single source of truth.

    Future await-chain / parent-tracking work will compose with this by
    introducing :mod:`contextvars`-backed lookups alongside the current
    asyncio.current_task() probe.
    """

    def __init__(self) -> None:
        self._task_ids: weakref.WeakKeyDictionary[asyncio.Task[Any], str] = (
            weakref.WeakKeyDictionary()
        )

    def register(self, task: asyncio.Task[Any], task_id: str) -> None:
        self._task_ids[task] = task_id

    def get(self, task: asyncio.Task[Any] | None) -> str | None:
        if task is None:
            return None
        return self._task_ids.get(task)

    def current(self) -> str | None:
        """asyncviz task_id of the task currently running on this loop, if any."""
        try:
            current = asyncio.current_task()
        except RuntimeError:
            return None
        return self.get(current)

    def clear(self) -> None:
        self._task_ids.clear()

    def __len__(self) -> int:
        return len(self._task_ids)


class CancellationContext:
    """Lightweight bookkeeping for cancellation-origin attribution.

    The dashboard lifespan calls :meth:`begin_shutdown` before tearing
    instrumentation down. Any cancellation that fires while
    ``shutdown_in_progress`` is set gets attributed as ``"shutdown"`` — the
    heartbeat task is the canonical example; user code that happens to
    cancel a task mid-shutdown also lands here.

    Outside the shutdown window, we attribute every cancellation as
    ``"explicit"`` when ``task.cancelling()`` reports a pending request.
    More-specific origins (``"timeout"``, ``"parent"``) will require deeper
    instrumentation hooks and are deferred.
    """

    __slots__ = ("_lock", "_shutdown_in_progress")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._shutdown_in_progress = False

    @property
    def shutdown_in_progress(self) -> bool:
        return self._shutdown_in_progress

    def begin_shutdown(self) -> None:
        with self._lock:
            self._shutdown_in_progress = True

    def end_shutdown(self) -> None:
        with self._lock:
            self._shutdown_in_progress = False

    def attribute(self, task: asyncio.Task[Any]) -> str | None:
        """Best-effort cancellation-origin classification.

        Called from the done-callback only when ``task.cancelled()`` is
        already True — so the caller has already proved that *something*
        cancelled this task. We're only deciding *what*.
        """
        if self._shutdown_in_progress:
            return "shutdown"
        with contextlib.suppress(AttributeError):
            # ``task.cancelling()`` returns the number of cancel() calls
            # minus uncancel() calls. > 0 means cancellation was requested
            # externally and the request was honored.
            if task.cancelling() > 0:
                return "explicit"
        # Fallback: cancelled() is True but no pending request — most
        # likely an old delivery that's already been consumed. Still mark
        # explicit so the frontend has *something* to show.
        return "explicit"
