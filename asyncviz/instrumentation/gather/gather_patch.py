"""Monkey-patch ``asyncio.gather`` to emit AsyncViz events on every
fanout / completion / cancellation / failure.

Patching strategy:

* Replace the module attribute ``asyncio.gather`` with an instrumented
  wrapper. The original is saved on the engine; ``unpatch()`` restores
  it atomically.
* The wrapper is *synchronous* — same as the stdlib ``gather`` itself.
  It coerces every input to an ``asyncio.Future`` (delegating to
  ``asyncio.ensure_future``), allocates a gather id, registers the
  children, and finally calls the original ``gather`` with the coerced
  list. We never wrap with ``async def`` because that would change
  the public type ``gather`` returns — code that does
  ``fut = asyncio.gather(...); ... ; await fut`` would break.
* Per-child + per-gather completion is tracked via
  ``Future.add_done_callback``. Callbacks fire on the event loop; they
  emit events synchronously into the bus and never re-enter the patched
  gather (the re-entrancy guard catches that path defensively).
* Every callback path swallows its own exceptions — a bug here cannot
  break gather's user-visible semantics.
* Internal AsyncViz call sites that themselves use ``asyncio.gather``
  (the bus dispatcher, the queue dispatcher, the websocket broadcaster)
  set the ``_in_internal_gather`` ContextVar via
  :func:`suppress_gather_instrumentation`; the patched wrapper short-
  circuits to the original gather in that case, with zero event
  emission, breaking what would otherwise be an event-amplification loop.

Semantic invariants preserved:

* ``return_exceptions=True`` still bubbles per-child exceptions into
  the result list.
* ``return_exceptions=False`` still propagates the first failure into
  the gather future.
* Cancellation of the gather future still propagates to every child.
* Result ordering still matches positional argument order.
* The empty-args case (``gather()``) still returns a pre-completed
  future immediately.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from typing import Any

from asyncviz.instrumentation.gather.gather_configuration import (
    DEFAULT_GATHER_CONFIG,
    GatherInstrumentationConfig,
)
from asyncviz.instrumentation.gather.gather_internal import is_internal_gather
from asyncviz.instrumentation.gather.gather_observability import get_gather_metrics
from asyncviz.instrumentation.gather.gather_registry import (
    GatherRegistry,
    get_default_gather_registry,
)
from asyncviz.instrumentation.gather.gather_tracing import (
    record_gather_trace,
    set_gather_trace_enabled,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models.gather import (
    GatherCancelledEvent,
    GatherChildAttachedEvent,
    GatherChildCompletedEvent,
    GatherCompletedEvent,
    GatherCreatedEvent,
    GatherFailedEvent,
    GatherWaitStartedEvent,
)
from asyncviz.runtime.lineage import current_runtime_task
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.gather.patch")


# Thread-local re-entrancy guard so an event publisher that itself
# touches gather can't trigger an emit-publish-emit loop.
_in_instrumentation = threading.local()


def _begin_instrumented() -> bool:
    if getattr(_in_instrumentation, "active", False):
        return False
    _in_instrumentation.active = True
    return True


def _end_instrumented() -> None:
    _in_instrumentation.active = False


TaskIdResolver = Callable[[object], str | None]
"""Strategy hook: given a Future/Task child, return its task id or None.

Wired by the dashboard so resolved ids align with the timeline's
``runtime_task_id`` namespace. When ``None`` is returned, the patcher
falls back to a deterministic ``f"task-{id(child)}"`` id."""


def _default_task_id_resolver(child: object) -> str | None:
    name = getattr(child, "get_name", None)
    if callable(name):
        try:
            value = name()
        except Exception:
            return None
        if isinstance(value, str) and value:
            return value
    return None


class GatherInstrumentationEngine:
    """Reversible, idempotent patcher for ``asyncio.gather``."""

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        registry: GatherRegistry | None = None,
        config: GatherInstrumentationConfig = DEFAULT_GATHER_CONFIG,
        task_id_resolver: TaskIdResolver | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry or get_default_gather_registry()
        self._config = config
        self._resolve_child_id = task_id_resolver or _default_task_id_resolver
        self._lock = threading.Lock()
        self._patched = False
        self._original_gather: Callable[..., Any] | None = None

    # ── public lifecycle ──────────────────────────────────────────

    @property
    def is_patched(self) -> bool:
        return self._patched

    @property
    def bus(self) -> EventBus | None:
        return self._bus

    @property
    def registry(self) -> GatherRegistry:
        return self._registry

    @property
    def config(self) -> GatherInstrumentationConfig:
        return self._config

    def set_bus(self, bus: EventBus | None) -> None:
        """Late-bind / unbind the event bus. Safe while patched."""
        self._bus = bus

    def set_task_id_resolver(self, resolver: TaskIdResolver | None) -> None:
        """Hot-swap the child-id resolver. Useful for tests + the dashboard
        wiring the asyncio patcher's TaskContext after construction."""
        self._resolve_child_id = resolver or _default_task_id_resolver

    def patch(self) -> None:
        """Install the instrumented gather on ``asyncio``."""
        with self._lock:
            if self._patched:
                return
            self._original_gather = asyncio.gather
            engine = self
            original = self._original_gather

            def patched_gather(
                *coros_or_futures: Any,
                return_exceptions: bool = False,
            ) -> Any:
                if is_internal_gather():
                    get_gather_metrics().record_suppressed()
                    record_gather_trace("suppressed")
                    return original(
                        *coros_or_futures,
                        return_exceptions=return_exceptions,
                    )
                if not coros_or_futures:
                    # Empty-args path returns a pre-completed Future. Skip
                    # instrumentation entirely — there's nothing to wait on.
                    return original(return_exceptions=return_exceptions)
                try:
                    return engine._dispatch(
                        coros_or_futures,
                        return_exceptions,
                        original,
                    )
                except Exception as exc:  # pragma: no cover — defensive
                    # If instrumentation itself blows up, fall back to the
                    # unwrapped gather so user code keeps working.
                    logger.debug("gather instrumentation failed: %s", exc)
                    get_gather_metrics().record_dropped()
                    return original(
                        *coros_or_futures,
                        return_exceptions=return_exceptions,
                    )

            patched_gather.__doc__ = getattr(original, "__doc__", None)
            patched_gather.__qualname__ = getattr(
                original,
                "__qualname__",
                "patched_gather",
            )
            patched_gather.__name__ = getattr(original, "__name__", "gather")
            asyncio.gather = patched_gather  # type: ignore[assignment]
            if getattr(self._config, "trace_on_init", False):
                set_gather_trace_enabled(True)
            self._patched = True
            logger.debug("asyncio.gather patched")

    def unpatch(self) -> None:
        """Restore the original ``asyncio.gather``. Idempotent."""
        with self._lock:
            if not self._patched or self._original_gather is None:
                self._patched = False
                self._original_gather = None
                return
            asyncio.gather = self._original_gather  # type: ignore[assignment]
            self._original_gather = None
            self._patched = False
            logger.debug("asyncio.gather unpatched")

    # ── core dispatch ─────────────────────────────────────────────

    def _dispatch(
        self,
        coros_or_futures: tuple[Any, ...],
        return_exceptions: bool,
        original_gather: Callable[..., Any],
    ) -> Any:
        if not _begin_instrumented():
            # Nested gather emission from inside our own publish path —
            # just call original.
            get_gather_metrics().record_recursion_skip()
            return original_gather(
                *coros_or_futures,
                return_exceptions=return_exceptions,
            )
        try:
            # Coerce children to Futures so we have stable handles. asyncio
            # gather does the same thing internally — calling ensure_future
            # twice on a Task is a no-op, so we don't double-wrap.
            coerced: list[asyncio.Future[Any]] = []
            for child in coros_or_futures:
                try:
                    coerced.append(asyncio.ensure_future(child))
                except Exception:
                    # If we can't coerce one, abandon instrumentation and
                    # delegate to the stdlib gather — it'll raise with the
                    # same exception message + leak fewer surprises.
                    return original_gather(
                        *coros_or_futures,
                        return_exceptions=return_exceptions,
                    )

            child_ids: list[str] = []
            for child in coerced:
                resolved = self._resolve_child_id(child)
                child_ids.append(
                    resolved if isinstance(resolved, str) and resolved else f"task-{id(child)}",
                )

            parent_id = current_runtime_task() if self._config.capture_parent_task_id else None
            future = original_gather(*coerced, return_exceptions=return_exceptions)
            identity = self._registry.register(
                parent_task_id=parent_id,
                child_task_ids=child_ids,
                return_exceptions=return_exceptions,
                anchor=future,
            )
            get_gather_metrics().record_instrumented()
            record_gather_trace("gather-registered", identity.gather_id)
            started_at = time.monotonic()

            self._emit_created(identity)
            self._emit_children_attached(identity, child_ids)
            self._emit_wait_started(identity)

            for index, child in enumerate(coerced):
                child.add_done_callback(
                    _make_child_callback(self, identity.gather_id, index, child_ids[index]),
                )
            future.add_done_callback(
                _make_gather_callback(self, identity.gather_id, started_at),
            )
            return future
        finally:
            _end_instrumented()

    # ── emission helpers ──────────────────────────────────────────

    def _emit_created(self, identity: Any) -> None:
        if not self._config.emit_created:
            return
        try:
            self._publish(
                GatherCreatedEvent(
                    gather_id=identity.gather_id,
                    parent_task_id=identity.parent_task_id,
                    child_count=identity.child_count,
                    snapshot=_snapshot_dict(
                        gather_id=identity.gather_id,
                        parent_task_id=identity.parent_task_id,
                        child_count=identity.child_count,
                        completed=0,
                        cancelled=False,
                        failed=False,
                        return_exceptions=identity.return_exceptions,
                    ),
                    child_task_ids=identity.child_task_ids,
                    return_exceptions=identity.return_exceptions,
                ),
            )
            record_gather_trace("gather-created", identity.gather_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("gather created emission failed: %s", exc)

    def _emit_children_attached(
        self,
        identity: Any,
        child_ids: list[str],
    ) -> None:
        if not self._config.emit_child_attached:
            return
        metrics = get_gather_metrics()
        for index, cid in enumerate(child_ids):
            try:
                self._publish(
                    GatherChildAttachedEvent(
                        gather_id=identity.gather_id,
                        parent_task_id=identity.parent_task_id,
                        child_count=identity.child_count,
                        snapshot=_snapshot_dict(
                            gather_id=identity.gather_id,
                            parent_task_id=identity.parent_task_id,
                            child_count=identity.child_count,
                            completed=0,
                            cancelled=False,
                            failed=False,
                            return_exceptions=identity.return_exceptions,
                        ),
                        child_task_id=cid,
                        child_index=index,
                    ),
                )
                metrics.record_child_attached()
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("gather child attached emission failed: %s", exc)
        record_gather_trace("gather-child-attached", identity.gather_id)

    def _emit_wait_started(self, identity: Any) -> None:
        if not self._config.emit_wait_started:
            return
        try:
            self._publish(
                GatherWaitStartedEvent(
                    gather_id=identity.gather_id,
                    parent_task_id=identity.parent_task_id,
                    child_count=identity.child_count,
                    snapshot=_snapshot_dict(
                        gather_id=identity.gather_id,
                        parent_task_id=identity.parent_task_id,
                        child_count=identity.child_count,
                        completed=0,
                        cancelled=False,
                        failed=False,
                        return_exceptions=identity.return_exceptions,
                    ),
                ),
            )
            record_gather_trace("gather-wait-started", identity.gather_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("gather wait_started emission failed: %s", exc)

    def _emit_child_completed(
        self,
        gather_id: str,
        child_task_id: str,
        child_index: int,
        cancelled: bool,
        failed: bool,
    ) -> None:
        if not self._config.emit_child_completed:
            return
        identity = self._registry.get(gather_id)
        progress = self._registry.record_child_completed(gather_id)
        completed = progress[0] if progress is not None else 0
        try:
            self._publish(
                GatherChildCompletedEvent(
                    gather_id=gather_id,
                    parent_task_id=identity.parent_task_id if identity else None,
                    child_count=identity.child_count if identity else 0,
                    snapshot=_snapshot_dict(
                        gather_id=gather_id,
                        parent_task_id=identity.parent_task_id if identity else None,
                        child_count=identity.child_count if identity else 0,
                        completed=completed,
                        cancelled=False,
                        failed=False,
                        return_exceptions=identity.return_exceptions if identity else False,
                    ),
                    child_task_id=child_task_id,
                    child_index=child_index,
                    cancelled=cancelled,
                    failed=failed,
                    completed_count=completed,
                ),
            )
            get_gather_metrics().record_child_completed()
            record_gather_trace(
                "gather-child-completed",
                f"{gather_id}#{child_index}",
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("gather child completed emission failed: %s", exc)

    def _emit_gather_completed(self, gather_id: str, started_at: float) -> None:
        identity = self._registry.get(gather_id)
        progress = self._registry.progress(gather_id)
        completed, _total, cancelled_flag, failed_flag = (
            progress
            if progress is not None
            else (identity.child_count if identity else 0, 0, False, False)
        )
        duration = max(0.0, time.monotonic() - started_at)
        if not self._config.emit_completed:
            self._registry.forget(gather_id)
            return
        try:
            self._publish(
                GatherCompletedEvent(
                    gather_id=gather_id,
                    parent_task_id=identity.parent_task_id if identity else None,
                    child_count=identity.child_count if identity else 0,
                    snapshot=_snapshot_dict(
                        gather_id=gather_id,
                        parent_task_id=identity.parent_task_id if identity else None,
                        child_count=identity.child_count if identity else 0,
                        completed=completed,
                        cancelled=cancelled_flag,
                        failed=failed_flag,
                        return_exceptions=identity.return_exceptions if identity else False,
                    ),
                    completed_count=completed,
                    cancelled_children=int(cancelled_flag),
                    failed_children=int(failed_flag),
                    duration_seconds=duration,
                ),
            )
            get_gather_metrics().record_completed()
            record_gather_trace("gather-completed", gather_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("gather completed emission failed: %s", exc)
        finally:
            self._registry.forget(gather_id)
            get_gather_metrics().record_finalized()

    def _emit_gather_cancelled(self, gather_id: str, started_at: float) -> None:
        identity = self._registry.get(gather_id)
        progress = self._registry.progress(gather_id)
        completed = progress[0] if progress is not None else 0
        duration = max(0.0, time.monotonic() - started_at)
        if not self._config.emit_cancelled:
            self._registry.forget(gather_id)
            return
        try:
            self._registry.mark_terminal(gather_id, cancelled=True)
            self._publish(
                GatherCancelledEvent(
                    gather_id=gather_id,
                    parent_task_id=identity.parent_task_id if identity else None,
                    child_count=identity.child_count if identity else 0,
                    snapshot=_snapshot_dict(
                        gather_id=gather_id,
                        parent_task_id=identity.parent_task_id if identity else None,
                        child_count=identity.child_count if identity else 0,
                        completed=completed,
                        cancelled=True,
                        failed=False,
                        return_exceptions=identity.return_exceptions if identity else False,
                    ),
                    completed_count=completed,
                    duration_seconds=duration,
                ),
            )
            get_gather_metrics().record_cancelled()
            record_gather_trace("gather-cancelled", gather_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("gather cancelled emission failed: %s", exc)
        finally:
            self._registry.forget(gather_id)
            get_gather_metrics().record_finalized()

    def _emit_gather_failed(
        self,
        gather_id: str,
        started_at: float,
        exception: BaseException,
    ) -> None:
        identity = self._registry.get(gather_id)
        progress = self._registry.progress(gather_id)
        completed = progress[0] if progress is not None else 0
        duration = max(0.0, time.monotonic() - started_at)
        if not self._config.emit_failed:
            self._registry.forget(gather_id)
            return
        try:
            self._registry.mark_terminal(gather_id, failed=True)
            self._publish(
                GatherFailedEvent(
                    gather_id=gather_id,
                    parent_task_id=identity.parent_task_id if identity else None,
                    child_count=identity.child_count if identity else 0,
                    snapshot=_snapshot_dict(
                        gather_id=gather_id,
                        parent_task_id=identity.parent_task_id if identity else None,
                        child_count=identity.child_count if identity else 0,
                        completed=completed,
                        cancelled=False,
                        failed=True,
                        return_exceptions=identity.return_exceptions if identity else False,
                    ),
                    completed_count=completed,
                    duration_seconds=duration,
                    exception_type=(
                        type(exception).__name__ if self._config.capture_exception_type else None
                    ),
                ),
            )
            get_gather_metrics().record_failed()
            record_gather_trace("gather-failed", gather_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("gather failed emission failed: %s", exc)
        finally:
            self._registry.forget(gather_id)
            get_gather_metrics().record_finalized()

    def _publish(self, event: Any) -> None:
        if self._bus is None:
            get_gather_metrics().record_dropped()
            record_gather_trace("event-dropped", "no bus")
            return
        try:
            self._bus.publish(event)
            get_gather_metrics().record_event()
        except Exception as exc:  # pragma: no cover — defensive
            get_gather_metrics().record_dropped()
            record_gather_trace("event-dropped", str(exc))


# ── done-callback factories ───────────────────────────────────────


def _make_child_callback(
    engine: GatherInstrumentationEngine,
    gather_id: str,
    child_index: int,
    child_task_id: str,
):
    def _on_done(future: asyncio.Future[Any]) -> None:
        cancelled = False
        failed = False
        try:
            if future.cancelled():
                cancelled = True
            else:
                exc = future.exception()
                if exc is not None and not isinstance(exc, asyncio.CancelledError):
                    failed = True
                elif isinstance(exc, asyncio.CancelledError):
                    cancelled = True
        except asyncio.CancelledError:
            cancelled = True
        except Exception:  # pragma: no cover — defensive
            failed = True
        try:
            engine._emit_child_completed(
                gather_id,
                child_task_id,
                child_index,
                cancelled,
                failed,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("gather child callback failed: %s", exc)

    return _on_done


def _make_gather_callback(
    engine: GatherInstrumentationEngine,
    gather_id: str,
    started_at: float,
):
    def _on_done(future: asyncio.Future[Any]) -> None:
        try:
            if future.cancelled():
                engine._emit_gather_cancelled(gather_id, started_at)
                return
            try:
                exc = future.exception()
            except asyncio.CancelledError:
                engine._emit_gather_cancelled(gather_id, started_at)
                return
            if exc is not None:
                # CancelledError sometimes surfaces as exception() (not
                # cancelled()) when ``_GatheringFuture`` propagates its
                # children's cancellation. Treat that as cancelled so
                # the metric counters match the user's mental model.
                if isinstance(exc, asyncio.CancelledError):
                    engine._emit_gather_cancelled(gather_id, started_at)
                    return
                engine._emit_gather_failed(gather_id, started_at, exc)
                return
            engine._emit_gather_completed(gather_id, started_at)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("gather completion callback failed: %s", exc)
            engine._registry.forget(gather_id)

    return _on_done


# ── snapshot helper ───────────────────────────────────────────────


def _snapshot_dict(
    *,
    gather_id: str,
    parent_task_id: str | None,
    child_count: int,
    completed: int,
    cancelled: bool,
    failed: bool,
    return_exceptions: bool,
) -> dict[str, Any]:
    pending = max(0, child_count - completed)
    return {
        "gather_id": gather_id,
        "parent_task_id": parent_task_id,
        "child_count": child_count,
        "completed_count": completed,
        "pending_count": pending,
        "cancelled": cancelled,
        "failed": failed,
        "return_exceptions": return_exceptions,
    }
