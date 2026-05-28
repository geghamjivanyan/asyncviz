"""Task-instrumentation compatibility bridge.

uvloop reimplements task creation in C; AsyncViz instruments tasks
via :meth:`AbstractEventLoop.set_task_factory`. Both loops accept
the same factory interface, so the bridge is mostly an *adapter*:

* validate the loop supports ``set_task_factory`` (uvloop does;
  some pure-Python alternatives don't),
* install AsyncViz's factory + remember the previous one,
* expose lifecycle counters (tasks created, cancelled, completed),
* offer :meth:`restore` so test harnesses can roll back cleanly.

The bridge stores zero per-task state — counters are aggregate.
Per-task instrumentation belongs in :mod:`asyncviz.runtime.tasks`.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass

TaskFactory = Callable[
    [asyncio.AbstractEventLoop, "asyncio.coroutines"],  # type: ignore[name-defined]
    asyncio.Task,
]


@dataclass(frozen=True, slots=True)
class TaskBridgeStats:
    tasks_created: int
    tasks_cancelled: int
    tasks_completed: int
    tasks_failed: int
    installed: bool


class LoopTaskBridge:
    """Wraps :meth:`AbstractEventLoop.set_task_factory`."""

    __slots__ = (
        "_factory",
        "_installed",
        "_lock",
        "_loop_ref",
        "_previous_factory",
        "_tasks_cancelled",
        "_tasks_completed",
        "_tasks_created",
        "_tasks_failed",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._installed = False
        self._previous_factory: TaskFactory | None = None
        self._loop_ref: asyncio.AbstractEventLoop | None = None
        self._factory: TaskFactory | None = None
        self._tasks_created = 0
        self._tasks_cancelled = 0
        self._tasks_completed = 0
        self._tasks_failed = 0

    def install(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        factory: TaskFactory | None = None,
    ) -> bool:
        """Install the bridge on ``loop``. Returns ``True`` when
        installed; ``False`` when the loop doesn't accept a factory
        (rare — only some non-asyncio loops)."""
        if self._installed:
            return True
        if not hasattr(loop, "set_task_factory"):
            return False
        with self._lock:
            previous = (
                loop.get_task_factory()
                if hasattr(loop, "get_task_factory")
                else None
            )
            self._previous_factory = previous
            self._loop_ref = loop
            self._factory = factory or self._default_factory
            try:
                loop.set_task_factory(self._wrapped_factory)
            except Exception:
                return False
            self._installed = True
        return True

    def restore(self) -> bool:
        """Roll back to the previous factory. Returns ``True`` when
        a restore actually happened."""
        if not self._installed:
            return False
        loop = self._loop_ref
        if loop is None:
            return False
        with self._lock:
            with contextlib.suppress(Exception):
                loop.set_task_factory(self._previous_factory)
            self._installed = False
        return True

    def record_task_completed(self, task: asyncio.Task) -> None:
        """Increment the appropriate counter for a finalized task."""
        with self._lock:
            if task.cancelled():
                self._tasks_cancelled += 1
            elif task.exception() is not None:
                self._tasks_failed += 1
            else:
                self._tasks_completed += 1

    def stats(self) -> TaskBridgeStats:
        with self._lock:
            return TaskBridgeStats(
                tasks_created=self._tasks_created,
                tasks_cancelled=self._tasks_cancelled,
                tasks_completed=self._tasks_completed,
                tasks_failed=self._tasks_failed,
                installed=self._installed,
            )

    def reset(self) -> None:
        with self._lock:
            self._tasks_created = 0
            self._tasks_cancelled = 0
            self._tasks_completed = 0
            self._tasks_failed = 0

    # ── internals ────────────────────────────────────────────────

    def _wrapped_factory(
        self,
        loop: asyncio.AbstractEventLoop,
        coro: object,
        **kwargs: object,
    ) -> asyncio.Task:
        with self._lock:
            self._tasks_created += 1
        factory = self._factory or self._default_factory
        task = factory(loop, coro, **kwargs)  # type: ignore[arg-type]
        # Attach the completion callback so we update the counters
        # when the task finalizes. We use a weak callback signature
        # to avoid retaining the bridge on the task indefinitely.
        task.add_done_callback(self._on_task_done)
        return task

    def _on_task_done(self, task: asyncio.Task) -> None:
        with contextlib.suppress(Exception):
            self.record_task_completed(task)

    @staticmethod
    def _default_factory(
        loop: asyncio.AbstractEventLoop,
        coro: object,
        **kwargs: object,
    ) -> asyncio.Task:
        # ``Task`` accepts ``name``/``context`` kwargs introduced in
        # 3.11; pass them through for forward-compat.
        return asyncio.Task(coro, loop=loop, **kwargs)  # type: ignore[arg-type]
