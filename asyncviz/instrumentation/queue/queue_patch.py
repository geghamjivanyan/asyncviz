"""Monkey-patch ``asyncio.Queue`` (+ ``LifoQueue`` / ``PriorityQueue``)
to emit AsyncViz events on every put/get/task_done.

Patching strategy:

* We do NOT subclass ``asyncio.Queue``. Replacing the original module
  attribute would still leave existing code using the unwrapped
  class. Instead we *patch the methods on the original classes* —
  every instance, past + future, picks up the instrumentation
  without recompiling user code.
* The patch records the originals on the engine; ``unpatch()``
  restores them atomically.
* Per-call recursion is guarded by a thread-local flag so an event
  publisher that ends up calling Queue internally (e.g. an internal
  event queue) never recurses into itself.
* Every callback path swallows its own exceptions — a bug in the
  instrumentation can never break user queue semantics.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from asyncviz.instrumentation.queue.queue_configuration import (
    DEFAULT_QUEUE_CONFIG,
    QueueInstrumentationConfig,
)
from asyncviz.instrumentation.queue.queue_internal import is_queue_internal
from asyncviz.instrumentation.queue.queue_observability import get_queue_metrics
from asyncviz.instrumentation.queue.queue_registry import (
    QueueRegistry,
    get_default_queue_registry,
)
from asyncviz.instrumentation.queue.queue_state import snapshot_queue
from asyncviz.instrumentation.queue.queue_tracing import record_queue_trace
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models.queue import (
    QueueCancelledEvent,
    QueueCreatedEvent,
    QueueEmptyWaitEvent,
    QueueFullWaitEvent,
    QueueGetEvent,
    QueuePutEvent,
    QueueTaskDoneEvent,
)
from asyncviz.runtime.lineage import current_runtime_task
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.queue.patch")

# Re-entrancy guard so the instrumentation never publishes against
# itself (e.g. the in-process event bus uses an asyncio.Queue under
# the hood).
_in_instrumentation = threading.local()


def _begin_instrumented() -> bool:
    if getattr(_in_instrumentation, "active", False):
        return False
    _in_instrumentation.active = True
    return True


def _end_instrumented() -> None:
    _in_instrumentation.active = False


# Task-local flag that suppresses the inner put_nowait / get_nowait emission
# when the call is made by an outer patched put / get. CPython's
# ``asyncio.Queue.put`` ends with ``return self.put_nowait(item)`` (and ``get``
# mirrors it). Because we patch both, the outer + inner methods would each
# emit a "put" event for one logical operation. A ContextVar is the right
# scope here: it's per-task (so concurrent tasks don't suppress each other)
# and survives the ``await`` inside ``original_put``.
_in_outer_put: ContextVar[bool] = ContextVar("_in_outer_put", default=False)
_in_outer_get: ContextVar[bool] = ContextVar("_in_outer_get", default=False)


PATCHED_CLASSES: tuple[type, ...] = (
    asyncio.Queue,
    asyncio.LifoQueue,
    asyncio.PriorityQueue,
)


class QueueInstrumentationEngine:
    """Reversible, idempotent patcher for ``asyncio.Queue`` + subclasses.

    Holds the original method references + the active engine state.
    Construct one per :func:`asyncviz.start` invocation so multiple
    runtimes don't fight over the global classes.
    """

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        registry: QueueRegistry | None = None,
        config: QueueInstrumentationConfig = DEFAULT_QUEUE_CONFIG,
    ) -> None:
        self._bus = bus
        self._registry = registry or get_default_queue_registry()
        self._config = config
        self._lock = threading.Lock()
        self._patched = False
        self._originals: dict[str, Callable[..., Any]] = {}

    # ── public lifecycle ──────────────────────────────────────────

    @property
    def is_patched(self) -> bool:
        return self._patched

    @property
    def bus(self) -> EventBus | None:
        return self._bus

    @property
    def registry(self) -> QueueRegistry:
        return self._registry

    @property
    def config(self) -> QueueInstrumentationConfig:
        return self._config

    def set_bus(self, bus: EventBus | None) -> None:
        """Late-bind / unbind the event bus. Safe while patched."""
        self._bus = bus

    def patch(self) -> None:
        """Install the instrumented methods on ``asyncio.Queue``."""
        with self._lock:
            if self._patched:
                return
            engine = self
            base = asyncio.Queue
            self._originals = {
                "__init__": base.__init__,
                "put": base.put,
                "put_nowait": base.put_nowait,
                "get": base.get,
                "get_nowait": base.get_nowait,
                "task_done": base.task_done,
            }

            original_init = self._originals["__init__"]
            original_put = self._originals["put"]
            original_put_nowait = self._originals["put_nowait"]
            original_get = self._originals["get"]
            original_get_nowait = self._originals["get_nowait"]
            original_task_done = self._originals["task_done"]

            def patched_init(self_queue: asyncio.Queue, *args, **kwargs):
                original_init(self_queue, *args, **kwargs)
                if is_queue_internal(self_queue):
                    return
                engine._on_created(self_queue)

            async def patched_put(self_queue: asyncio.Queue, item):
                if is_queue_internal(self_queue):
                    return await original_put(self_queue, item)
                snapshot_before = snapshot_queue(
                    self_queue,
                    queue_id=engine._safe_queue_id(self_queue),
                )
                full = (
                    snapshot_before.maxsize > 0 and snapshot_before.size >= snapshot_before.maxsize
                )
                if full:
                    engine._emit_full_wait(self_queue)
                started = time.monotonic()
                token = _in_outer_put.set(True)
                try:
                    return await original_put(self_queue, item)
                except asyncio.CancelledError:
                    engine._emit_cancelled(self_queue, "put", started)
                    raise
                finally:
                    _in_outer_put.reset(token)
                    if full:
                        engine._emit_put(
                            self_queue,
                            nowait=False,
                            blocked=True,
                            wait_seconds=max(0.0, time.monotonic() - started),
                        )
                    else:
                        engine._emit_put(
                            self_queue,
                            nowait=False,
                            blocked=False,
                            wait_seconds=None,
                        )

            def patched_put_nowait(self_queue: asyncio.Queue, item):
                if is_queue_internal(self_queue):
                    return original_put_nowait(self_queue, item)
                if _in_outer_put.get():
                    # Called from inside patched_put — the outer call owns
                    # the emission. Avoid double-counting one logical put.
                    return original_put_nowait(self_queue, item)
                try:
                    return original_put_nowait(self_queue, item)
                finally:
                    engine._emit_put(
                        self_queue,
                        nowait=True,
                        blocked=False,
                        wait_seconds=None,
                    )

            async def patched_get(self_queue: asyncio.Queue):
                if is_queue_internal(self_queue):
                    return await original_get(self_queue)
                snapshot_before = snapshot_queue(
                    self_queue,
                    queue_id=engine._safe_queue_id(self_queue),
                )
                empty = snapshot_before.size == 0
                if empty:
                    engine._emit_empty_wait(self_queue)
                started = time.monotonic()
                token = _in_outer_get.set(True)
                try:
                    result = await original_get(self_queue)
                except asyncio.CancelledError:
                    engine._emit_cancelled(self_queue, "get", started)
                    raise
                finally:
                    _in_outer_get.reset(token)
                if empty:
                    engine._emit_get(
                        self_queue,
                        nowait=False,
                        blocked=True,
                        wait_seconds=max(0.0, time.monotonic() - started),
                    )
                else:
                    engine._emit_get(
                        self_queue,
                        nowait=False,
                        blocked=False,
                        wait_seconds=None,
                    )
                return result

            def patched_get_nowait(self_queue: asyncio.Queue):
                if is_queue_internal(self_queue):
                    return original_get_nowait(self_queue)
                if _in_outer_get.get():
                    return original_get_nowait(self_queue)
                result = original_get_nowait(self_queue)
                engine._emit_get(
                    self_queue,
                    nowait=True,
                    blocked=False,
                    wait_seconds=None,
                )
                return result

            def patched_task_done(self_queue: asyncio.Queue):
                if is_queue_internal(self_queue):
                    return original_task_done(self_queue)
                try:
                    return original_task_done(self_queue)
                finally:
                    engine._emit_task_done(self_queue)

            for cls in PATCHED_CLASSES:
                cls.__init__ = patched_init  # type: ignore[method-assign]
                cls.put = patched_put  # type: ignore[method-assign]
                cls.put_nowait = patched_put_nowait  # type: ignore[method-assign]
                cls.get = patched_get  # type: ignore[method-assign]
                cls.get_nowait = patched_get_nowait  # type: ignore[method-assign]
                cls.task_done = patched_task_done  # type: ignore[method-assign]

            self._patched = True
            logger.debug("asyncio.Queue patched")

    def unpatch(self) -> None:
        """Restore the original methods. Idempotent."""
        with self._lock:
            if not self._patched:
                return
            for cls in PATCHED_CLASSES:
                for name, original in self._originals.items():
                    setattr(cls, name, original)
            self._originals.clear()
            self._patched = False
            logger.debug("asyncio.Queue unpatched")

    # ── internals ─────────────────────────────────────────────────

    def _safe_queue_id(self, queue: asyncio.Queue) -> str:
        identity = self._registry.get(queue)
        if identity is not None:
            return identity.queue_id
        # Register lazily for queues that were created before the
        # patch attached or via ``__init__`` paths we couldn't see.
        return self._register(queue).queue_id

    def _register(self, queue: asyncio.Queue) -> Any:
        creator = current_runtime_task() if self._config.capture_creator_task_id else None
        identity = self._registry.register(queue, creator_task_id=creator)
        get_queue_metrics().record_registered()
        record_queue_trace("queue-registered", identity.queue_id)
        return identity

    def _on_created(self, queue: asyncio.Queue) -> None:
        if not _begin_instrumented():
            get_queue_metrics().record_recursion_skip()
            record_queue_trace("recursion-skip", "queue-init")
            return
        try:
            identity = self._register(queue)
            if not self._config.emit_created:
                return
            self._publish(
                QueueCreatedEvent(
                    queue_id=identity.queue_id,
                    queue_kind=identity.queue_kind,
                    maxsize=identity.maxsize,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(
                        snapshot_queue(queue, queue_id=identity.queue_id),
                    ),
                    creator_task_id=identity.creator_task_id,
                    name=identity.name,
                ),
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("queue created instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_put(
        self,
        queue: asyncio.Queue,
        *,
        nowait: bool,
        blocked: bool,
        wait_seconds: float | None,
    ) -> None:
        if not self._config.emit_put_get:
            return
        if not _begin_instrumented():
            get_queue_metrics().record_recursion_skip()
            return
        try:
            queue_id = self._safe_queue_id(queue)
            identity = self._registry.get_by_id(queue_id)
            event = QueuePutEvent(
                queue_id=queue_id,
                queue_kind=identity.queue_kind if identity else "unknown",
                maxsize=identity.maxsize if identity else 0,
                task_id=current_runtime_task(),
                snapshot=_snapshot_dict(snapshot_queue(queue, queue_id=queue_id)),
                nowait=nowait,
                blocked=blocked,
                wait_seconds=wait_seconds,
            )
            self._publish(event)
            get_queue_metrics().record_put(blocked=blocked)
            record_queue_trace("queue-put", f"{queue_id} blocked={blocked}")
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("queue put instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_get(
        self,
        queue: asyncio.Queue,
        *,
        nowait: bool,
        blocked: bool,
        wait_seconds: float | None,
    ) -> None:
        if not self._config.emit_put_get:
            return
        if not _begin_instrumented():
            get_queue_metrics().record_recursion_skip()
            return
        try:
            queue_id = self._safe_queue_id(queue)
            identity = self._registry.get_by_id(queue_id)
            event = QueueGetEvent(
                queue_id=queue_id,
                queue_kind=identity.queue_kind if identity else "unknown",
                maxsize=identity.maxsize if identity else 0,
                task_id=current_runtime_task(),
                snapshot=_snapshot_dict(snapshot_queue(queue, queue_id=queue_id)),
                nowait=nowait,
                blocked=blocked,
                wait_seconds=wait_seconds,
            )
            self._publish(event)
            get_queue_metrics().record_get(blocked=blocked)
            record_queue_trace("queue-get", f"{queue_id} blocked={blocked}")
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("queue get instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_full_wait(self, queue: asyncio.Queue) -> None:
        if not self._config.emit_wait_events:
            return
        if not _begin_instrumented():
            return
        try:
            queue_id = self._safe_queue_id(queue)
            identity = self._registry.get_by_id(queue_id)
            self._publish(
                QueueFullWaitEvent(
                    queue_id=queue_id,
                    queue_kind=identity.queue_kind if identity else "unknown",
                    maxsize=identity.maxsize if identity else 0,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(snapshot_queue(queue, queue_id=queue_id)),
                ),
            )
            get_queue_metrics().record_full_wait()
            record_queue_trace("queue-full-wait", queue_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("queue full_wait instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_empty_wait(self, queue: asyncio.Queue) -> None:
        if not self._config.emit_wait_events:
            return
        if not _begin_instrumented():
            return
        try:
            queue_id = self._safe_queue_id(queue)
            identity = self._registry.get_by_id(queue_id)
            self._publish(
                QueueEmptyWaitEvent(
                    queue_id=queue_id,
                    queue_kind=identity.queue_kind if identity else "unknown",
                    maxsize=identity.maxsize if identity else 0,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(snapshot_queue(queue, queue_id=queue_id)),
                ),
            )
            get_queue_metrics().record_empty_wait()
            record_queue_trace("queue-empty-wait", queue_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("queue empty_wait instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_task_done(self, queue: asyncio.Queue) -> None:
        if not self._config.emit_task_done:
            return
        if not _begin_instrumented():
            return
        try:
            queue_id = self._safe_queue_id(queue)
            identity = self._registry.get_by_id(queue_id)
            self._publish(
                QueueTaskDoneEvent(
                    queue_id=queue_id,
                    queue_kind=identity.queue_kind if identity else "unknown",
                    maxsize=identity.maxsize if identity else 0,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(snapshot_queue(queue, queue_id=queue_id)),
                ),
            )
            get_queue_metrics().record_task_done()
            record_queue_trace("queue-task-done", queue_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("queue task_done instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_cancelled(
        self,
        queue: asyncio.Queue,
        operation: str,
        started: float,
    ) -> None:
        if not self._config.emit_cancelled:
            return
        if not _begin_instrumented():
            return
        try:
            queue_id = self._safe_queue_id(queue)
            identity = self._registry.get_by_id(queue_id)
            wait = max(0.0, time.monotonic() - started)
            self._publish(
                QueueCancelledEvent(
                    queue_id=queue_id,
                    queue_kind=identity.queue_kind if identity else "unknown",
                    maxsize=identity.maxsize if identity else 0,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(snapshot_queue(queue, queue_id=queue_id)),
                    operation=operation,  # type: ignore[arg-type]
                    wait_seconds=wait,
                ),
            )
            get_queue_metrics().record_cancelled()
            record_queue_trace("queue-cancelled", f"{queue_id} op={operation}")
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("queue cancelled instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _publish(self, event: Any) -> None:
        if self._bus is None:
            get_queue_metrics().record_dropped()
            record_queue_trace("event-dropped", "no bus")
            return
        try:
            self._bus.publish(event)
            get_queue_metrics().record_event()
        except Exception as exc:  # pragma: no cover — defensive
            get_queue_metrics().record_dropped()
            record_queue_trace("event-dropped", str(exc))


def _snapshot_dict(snap: Any) -> dict[str, Any]:
    return {
        "size": snap.size,
        "maxsize": snap.maxsize,
        "blocked_putters": snap.blocked_putters,
        "blocked_getters": snap.blocked_getters,
        "unfinished_tasks": snap.unfinished_tasks,
    }
