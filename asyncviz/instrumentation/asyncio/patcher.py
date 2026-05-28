from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Any

from asyncviz.instrumentation.asyncio.context import CancellationContext, TaskContext
from asyncviz.instrumentation.asyncio.create_task import (
    CreateTaskFn,
    make_instrumented_create_task,
)
from asyncviz.runtime.events import EventBus
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.asyncio.patcher")


class AsyncioPatcher:
    """Reversible, idempotent patcher for ``asyncio.create_task``.

    Process-global by nature (since the module attribute is shared), but the
    patcher instance owns the original reference and the WeakKeyDictionary
    of task ids. Repeated ``patch()`` is a no-op; ``unpatch()`` restores
    whatever ``asyncio.create_task`` was at the moment of the original patch.

    Thread-safe: ``patch`` / ``unpatch`` are guarded by a single lock so
    concurrent lifecycle transitions can't race.
    """

    def __init__(self, bus: EventBus, *, runtime_id: uuid.UUID | None = None) -> None:
        self._bus = bus
        self._runtime_id = runtime_id or uuid.uuid4()
        self._lock = threading.Lock()
        self._context = TaskContext()
        self._cancellation_context = CancellationContext()
        self._original: CreateTaskFn | None = None
        self._patched_callable: CreateTaskFn | None = None
        self._patched = False

    # ── lifecycle ────────────────────────────────────────────────────────
    def patch(self) -> None:
        """Install the instrumented ``asyncio.create_task``. Idempotent."""
        with self._lock:
            if self._patched:
                return
            self._original = asyncio.create_task  # type: ignore[assignment]
            wrapped = make_instrumented_create_task(
                self._original,
                bus=self._bus,
                context=self._context,
                cancellation_context=self._cancellation_context,
                runtime_id=self._runtime_id,
            )
            asyncio.create_task = wrapped  # type: ignore[assignment]
            self._patched_callable = wrapped
            self._patched = True
            logger.debug("asyncio.create_task patched (runtime_id=%s)", self._runtime_id)

    def unpatch(self) -> None:
        """Restore the original ``asyncio.create_task``. Idempotent.

        If a third party patched on top of us in the meantime, we won't
        undo their patch — we only undo our own. Cooperation, not chaos.
        """
        with self._lock:
            if not self._patched:
                return
            # Only restore if our wrapper is still installed; otherwise leave
            # whatever the most recent patcher set in place.
            current: Any = asyncio.create_task
            if current is self._patched_callable and self._original is not None:
                asyncio.create_task = self._original  # type: ignore[assignment]
            else:
                logger.debug("asyncio.create_task was replaced after patch — leaving in place")
            self._original = None
            self._patched_callable = None
            self._patched = False
            self._context.clear()
            logger.debug("asyncio.create_task unpatched")

    # ── observability ────────────────────────────────────────────────────
    @property
    def is_patched(self) -> bool:
        return self._patched

    @property
    def runtime_id(self) -> uuid.UUID:
        return self._runtime_id

    @property
    def context(self) -> TaskContext:
        return self._context

    @property
    def cancellation_context(self) -> CancellationContext:
        return self._cancellation_context
