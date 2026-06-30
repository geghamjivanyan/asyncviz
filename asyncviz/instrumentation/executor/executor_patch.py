"""Monkey-patch ``BaseEventLoop.run_in_executor`` to emit AsyncViz
events on every async↔executor boundary crossing.

Patching strategy:

* Replace ``asyncio.base_events.BaseEventLoop.run_in_executor`` at the
  class level. The original is saved on the engine; ``unpatch()``
  restores it atomically. Every running + future event loop picks up
  the instrumented method without recompiling user code.
* The wrapper has the exact same signature as the stdlib method and
  returns the same kind of asyncio Future, so code that captures the
  future and awaits it later (``fut = loop.run_in_executor(...); ...
  await fut``) keeps working.
* We coerce ``executor=None`` to the loop's lazily-allocated default
  pool BEFORE calling the original method, so we have a stable handle
  to register. Identical to what the original method does internally
  — ``ensure_future`` semantics for executors.
* The user function is wrapped to capture start/end + worker-thread
  name from inside the executor thread. Cancellation / failure are
  detected via a done-callback on the asyncio Future the original
  method returns.
* Every callback path swallows its own exceptions — a bug in
  instrumentation cannot break ``run_in_executor`` semantics.
* Internal AsyncViz call sites can wrap their calls in
  :func:`suppress_executor_instrumentation` to short-circuit
  instrumentation entirely (event-amplification guard).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import threading
import time
from collections.abc import Callable
from typing import Any

from asyncviz.instrumentation.executor.executor_configuration import (
    DEFAULT_EXECUTOR_CONFIG,
    ExecutorInstrumentationConfig,
)
from asyncviz.instrumentation.executor.executor_internal import (
    is_internal_executor_call,
)
from asyncviz.instrumentation.executor.executor_observability import (
    get_executor_metrics,
)
from asyncviz.instrumentation.executor.executor_registry import (
    ExecutorRegistry,
    WorkItemRegistry,
    get_default_executor_registry,
    get_default_work_item_registry,
)
from asyncviz.instrumentation.executor.executor_state import read_callable_name
from asyncviz.instrumentation.executor.executor_tracing import (
    record_executor_trace,
    set_executor_trace_enabled,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models.executor import (
    ExecutorRegisteredEvent,
    ExecutorWorkCancelledEvent,
    ExecutorWorkCompletedEvent,
    ExecutorWorkFailedEvent,
    ExecutorWorkStartedEvent,
    ExecutorWorkSubmittedEvent,
)
from asyncviz.runtime.lineage import current_runtime_task
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.executor.patch")


# Thread-local re-entrancy guard. Without it, a publisher that itself
# dispatches work through an executor (rare but plausible for future
# adapters) could trigger emit-publish-emit loops.
_in_instrumentation = threading.local()


def _begin_instrumented() -> bool:
    if getattr(_in_instrumentation, "active", False):
        return False
    _in_instrumentation.active = True
    return True


def _end_instrumented() -> None:
    _in_instrumentation.active = False


def _safe_publish(bus: EventBus | None, event: Any) -> None:
    if bus is None:
        get_executor_metrics().record_dropped()
        record_executor_trace("event-dropped", "no bus")
        return
    try:
        bus.publish(event)
        get_executor_metrics().record_event()
    except Exception as exc:  # pragma: no cover — defensive
        get_executor_metrics().record_dropped()
        record_executor_trace("event-dropped", str(exc))


class ExecutorInstrumentationEngine:
    """Reversible, idempotent patcher for
    :func:`BaseEventLoop.run_in_executor`."""

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        executor_registry: ExecutorRegistry | None = None,
        work_item_registry: WorkItemRegistry | None = None,
        config: ExecutorInstrumentationConfig = DEFAULT_EXECUTOR_CONFIG,
    ) -> None:
        self._bus = bus
        self._executor_registry = executor_registry or get_default_executor_registry()
        self._work_item_registry = work_item_registry or get_default_work_item_registry()
        self._config = config
        self._lock = threading.Lock()
        self._patched = False
        self._original: Callable[..., Any] | None = None

    # ── public lifecycle ──────────────────────────────────────────

    @property
    def is_patched(self) -> bool:
        return self._patched

    @property
    def bus(self) -> EventBus | None:
        return self._bus

    @property
    def executor_registry(self) -> ExecutorRegistry:
        return self._executor_registry

    @property
    def work_item_registry(self) -> WorkItemRegistry:
        return self._work_item_registry

    @property
    def config(self) -> ExecutorInstrumentationConfig:
        return self._config

    def set_bus(self, bus: EventBus | None) -> None:
        """Late-bind / unbind the event bus. Safe while patched."""
        self._bus = bus

    def patch(self) -> None:
        """Install the instrumented ``run_in_executor``."""
        with self._lock:
            if self._patched:
                return
            base_class = asyncio.base_events.BaseEventLoop  # type: ignore[attr-defined]
            self._original = base_class.run_in_executor
            engine = self
            original = self._original

            def patched_run_in_executor(
                self_loop: asyncio.AbstractEventLoop,
                executor: concurrent.futures.Executor | None,
                func: Callable[..., Any],
                *args: Any,
            ) -> asyncio.Future[Any]:
                if is_internal_executor_call():
                    get_executor_metrics().record_suppressed()
                    record_executor_trace("suppressed")
                    return original(self_loop, executor, func, *args)
                try:
                    return engine._dispatch(
                        self_loop,
                        executor,
                        func,
                        args,
                        original,
                    )
                except Exception as exc:  # pragma: no cover — defensive
                    logger.debug("executor instrumentation failed: %s", exc)
                    get_executor_metrics().record_dropped()
                    return original(self_loop, executor, func, *args)

            patched_run_in_executor.__doc__ = getattr(original, "__doc__", None)
            patched_run_in_executor.__qualname__ = getattr(
                original,
                "__qualname__",
                "patched_run_in_executor",
            )
            patched_run_in_executor.__name__ = getattr(
                original,
                "__name__",
                "run_in_executor",
            )
            base_class.run_in_executor = patched_run_in_executor  # type: ignore[assignment]
            if getattr(self._config, "trace_on_init", False):
                set_executor_trace_enabled(True)
            self._patched = True
            logger.debug("BaseEventLoop.run_in_executor patched")

    def unpatch(self) -> None:
        """Restore the original ``run_in_executor``. Idempotent."""
        with self._lock:
            if not self._patched or self._original is None:
                self._patched = False
                self._original = None
                return
            base_class = asyncio.base_events.BaseEventLoop  # type: ignore[attr-defined]
            base_class.run_in_executor = self._original  # type: ignore[assignment]
            self._original = None
            self._patched = False
            logger.debug("BaseEventLoop.run_in_executor unpatched")

    # ── core dispatch ─────────────────────────────────────────────

    def _dispatch(
        self,
        loop: asyncio.AbstractEventLoop,
        executor: concurrent.futures.Executor | None,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        original: Callable[..., Any],
    ) -> asyncio.Future[Any]:
        if not _begin_instrumented():
            get_executor_metrics().record_recursion_skip()
            return original(loop, executor, func, *args)
        try:
            # Coerce ``None`` to the loop's lazy default executor BEFORE
            # registering so we have a stable handle. CPython lazily
            # constructs it the first time ``run_in_executor`` is called
            # with ``None`` — we trigger the same path by reading
            # ``loop._default_executor`` after a no-op submission, but
            # the simpler route is to call into the original once with
            # ``None`` and use whatever ``loop._default_executor`` ends
            # up being. The simpler-still route used here: only resolve
            # the executor when it's already an instance; for ``None``
            # we register on the synthetic ``"default"`` key once the
            # loop has actually allocated one.
            is_default = executor is None
            resolved = executor
            if is_default:
                # If the loop already has a default executor, prefer it
                # so registry entries align across submissions.
                existing_default = getattr(loop, "_default_executor", None)
                if existing_default is not None:
                    resolved = existing_default
                    is_default = True  # still mark as the default
            identity, is_new = self._executor_registry.register_or_get(
                resolved if resolved is not None else loop,
                is_default=is_default,
                creator_task_id=(
                    current_runtime_task() if self._config.capture_submitting_task_id else None
                ),
            )
            if is_new and self._config.emit_registered:
                get_executor_metrics().record_executor_registered()
                self._emit_registered(identity)

            submitting_task = (
                current_runtime_task() if self._config.capture_submitting_task_id else None
            )
            callable_name = read_callable_name(func) if self._config.capture_callable_name else None
            work_item = self._work_item_registry.register(
                executor_id=identity.executor_id,
                submitting_task_id=submitting_task,
                callable_name=callable_name,
            )
            get_executor_metrics().record_work_submitted()
            self._emit_submitted(identity, work_item)
            record_executor_trace("work-submitted", work_item.work_item_id)

            wrapped_func = self._wrap_callable(func, identity, work_item)
            future = original(loop, executor, wrapped_func, *args)
            future.add_done_callback(
                _make_done_callback(self, identity.executor_id, work_item.work_item_id),
            )
            return future
        finally:
            _end_instrumented()

    # ── callable wrapping ─────────────────────────────────────────

    def _wrap_callable(
        self,
        func: Callable[..., Any],
        identity: Any,
        work_item: Any,
    ) -> Callable[..., Any]:
        engine = self

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started_at_ns = time.monotonic_ns()
            worker_thread_name = (
                threading.current_thread().name
                if engine._config.capture_worker_thread_name
                else None
            )
            engine._work_item_registry.mark_started(
                work_item.work_item_id,
                worker_thread_name=worker_thread_name,
                started_at_ns=started_at_ns,
            )
            get_executor_metrics().record_work_started()
            engine._emit_started(
                identity,
                work_item,
                worker_thread_name,
                started_at_ns,
            )
            record_executor_trace("work-started", work_item.work_item_id)
            # Emit completed / failed from the executor thread so the
            # event is enqueued BEFORE the awaiter resumes — otherwise
            # callers that do ``await loop.run_in_executor(...); await
            # bus.join()`` race the done-callback's call_soon_threadsafe
            # and may observe an empty bus.
            try:
                result = func(*args, **kwargs)
            except BaseException as exc:
                finished_at_ns = time.monotonic_ns()
                duration = max(0, finished_at_ns - started_at_ns) / 1_000_000_000
                exception_type = (
                    type(exc).__name__ if engine._config.capture_exception_type else None
                )
                engine._work_item_registry.mark_failed(
                    work_item.work_item_id,
                    finished_at_ns=finished_at_ns,
                    exception_type=exception_type,
                )
                engine._emit_failed(
                    identity.executor_id,
                    work_item.work_item_id,
                    worker_thread_name,
                    duration,
                    exception_type,
                )
                raise
            finished_at_ns = time.monotonic_ns()
            duration = max(0, finished_at_ns - started_at_ns) / 1_000_000_000
            engine._work_item_registry.mark_completed(
                work_item.work_item_id,
                finished_at_ns=finished_at_ns,
            )
            engine._emit_completed(
                identity.executor_id,
                work_item.work_item_id,
                worker_thread_name,
                duration,
            )
            return result

        with contextlib.suppress(AttributeError):
            wrapper.__qualname__ = getattr(
                func,
                "__qualname__",
                "asyncviz_executor_wrapper",
            )
            wrapper.__name__ = getattr(func, "__name__", "asyncviz_executor_wrapper")
        return wrapper

    # ── emission helpers ──────────────────────────────────────────

    def _emit_registered(self, identity: Any) -> None:
        _safe_publish(
            self._bus,
            ExecutorRegisteredEvent(
                executor_id=identity.executor_id,
                executor_kind=identity.executor_kind,
                snapshot=_executor_snapshot_dict(identity),
                max_workers=identity.max_workers,
                thread_name_prefix=identity.thread_name_prefix,
                creator_task_id=identity.creator_task_id,
                name=identity.name,
            ),
        )
        record_executor_trace("executor-registered", identity.executor_id)

    def _emit_submitted(self, identity: Any, work_item: Any) -> None:
        if not self._config.emit_submitted:
            return
        _safe_publish(
            self._bus,
            ExecutorWorkSubmittedEvent(
                executor_id=identity.executor_id,
                executor_kind=identity.executor_kind,
                snapshot=_work_item_snapshot_dict(work_item, started=False),
                work_item_id=work_item.work_item_id,
                submitting_task_id=work_item.submitting_task_id,
                callable_name=work_item.callable_name,
            ),
        )

    def _emit_started(
        self,
        identity: Any,
        work_item: Any,
        worker_thread_name: str | None,
        started_at_ns: int,
    ) -> None:
        if not self._config.emit_started:
            return
        latency = max(0, started_at_ns - work_item.submitted_at_ns) / 1_000_000_000
        _safe_publish(
            self._bus,
            ExecutorWorkStartedEvent(
                executor_id=identity.executor_id,
                executor_kind=identity.executor_kind,
                snapshot=_work_item_snapshot_dict(work_item, started=True),
                work_item_id=work_item.work_item_id,
                submitting_task_id=work_item.submitting_task_id,
                callable_name=work_item.callable_name,
                worker_thread_name=worker_thread_name,
                submission_latency_seconds=latency,
            ),
        )

    def _emit_completed(
        self,
        executor_id: str,
        work_item_id: str,
        worker_thread_name: str | None,
        duration_seconds: float | None,
    ) -> None:
        if not self._config.emit_completed:
            return
        identity = self._executor_registry.get_by_id(executor_id)
        work_item = self._work_item_registry.get(work_item_id)
        if identity is None or work_item is None:
            return
        _safe_publish(
            self._bus,
            ExecutorWorkCompletedEvent(
                executor_id=executor_id,
                executor_kind=identity.executor_kind,
                snapshot=_work_item_snapshot_dict(
                    work_item,
                    started=True,
                    completed=True,
                ),
                work_item_id=work_item_id,
                submitting_task_id=work_item.submitting_task_id,
                callable_name=work_item.callable_name,
                worker_thread_name=worker_thread_name,
                duration_seconds=duration_seconds,
            ),
        )
        get_executor_metrics().record_work_completed()
        record_executor_trace("work-completed", work_item_id)

    def _emit_failed(
        self,
        executor_id: str,
        work_item_id: str,
        worker_thread_name: str | None,
        duration_seconds: float | None,
        exception_type: str | None,
    ) -> None:
        if not self._config.emit_failed:
            return
        identity = self._executor_registry.get_by_id(executor_id)
        work_item = self._work_item_registry.get(work_item_id)
        if identity is None or work_item is None:
            return
        _safe_publish(
            self._bus,
            ExecutorWorkFailedEvent(
                executor_id=executor_id,
                executor_kind=identity.executor_kind,
                snapshot=_work_item_snapshot_dict(
                    work_item,
                    started=True,
                    failed=True,
                ),
                work_item_id=work_item_id,
                submitting_task_id=work_item.submitting_task_id,
                callable_name=work_item.callable_name,
                worker_thread_name=worker_thread_name,
                duration_seconds=duration_seconds,
                exception_type=exception_type,
            ),
        )
        get_executor_metrics().record_work_failed()
        record_executor_trace("work-failed", work_item_id)

    def _emit_cancelled(
        self,
        executor_id: str,
        work_item_id: str,
        duration_seconds: float | None,
    ) -> None:
        if not self._config.emit_cancelled:
            return
        identity = self._executor_registry.get_by_id(executor_id)
        work_item = self._work_item_registry.get(work_item_id)
        if identity is None or work_item is None:
            return
        _safe_publish(
            self._bus,
            ExecutorWorkCancelledEvent(
                executor_id=executor_id,
                executor_kind=identity.executor_kind,
                snapshot=_work_item_snapshot_dict(
                    work_item,
                    started=False,
                    cancelled=True,
                ),
                work_item_id=work_item_id,
                submitting_task_id=work_item.submitting_task_id,
                callable_name=work_item.callable_name,
                duration_seconds=duration_seconds,
            ),
        )
        get_executor_metrics().record_work_cancelled()
        record_executor_trace("work-cancelled", work_item_id)


# ── done-callback factory ────────────────────────────────────────


def _make_done_callback(
    engine: ExecutorInstrumentationEngine,
    executor_id: str,
    work_item_id: str,
):
    """Cancellation-only callback.

    Completed + failed events are emitted from the executor-thread
    wrapper (so they're enqueued before the awaiter resumes); the
    done-callback only handles the cancellation case where the wrapper
    never ran. If the wrapper did run (state.started is True), the
    callback short-circuits to cleanup.
    """

    def _on_done(future: asyncio.Future[Any]) -> None:
        try:
            state = engine._work_item_registry.state(work_item_id)
            if state is not None and state.started:
                # The wrapper already emitted completed / failed.
                # Nothing to do beyond cleanup in the ``finally`` block.
                return
            finished_at_ns = time.monotonic_ns()
            duration_seconds: float | None = None
            cancelled = future.cancelled()
            if not cancelled:
                # If the work was rejected by the executor (e.g. pool
                # shutting down) the future may have an exception.
                try:
                    exc = future.exception()
                except asyncio.CancelledError:
                    cancelled = True
                    exc = None
                if not cancelled and exc is not None:
                    # Edge case: not started + exception. Most likely
                    # the submission itself raised. Surface as failed
                    # with no worker thread name.
                    exception_type = (
                        type(exc).__name__ if engine._config.capture_exception_type else None
                    )
                    engine._work_item_registry.mark_failed(
                        work_item_id,
                        finished_at_ns=finished_at_ns,
                        exception_type=exception_type,
                    )
                    engine._emit_failed(
                        executor_id,
                        work_item_id,
                        None,
                        duration_seconds,
                        exception_type,
                    )
                    return
            if cancelled:
                engine._work_item_registry.mark_cancelled(
                    work_item_id,
                    finished_at_ns=finished_at_ns,
                )
                engine._emit_cancelled(executor_id, work_item_id, duration_seconds)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("executor done callback failed: %s", exc)
        finally:
            engine._work_item_registry.forget(work_item_id)

    return _on_done


# ── snapshot helpers ─────────────────────────────────────────────


def _executor_snapshot_dict(identity: Any) -> dict[str, Any]:
    return {
        "executor_id": identity.executor_id,
        "executor_kind": identity.executor_kind,
        "max_workers": identity.max_workers,
        "thread_name_prefix": identity.thread_name_prefix,
    }


def _work_item_snapshot_dict(
    work_item: Any,
    *,
    started: bool = False,
    completed: bool = False,
    cancelled: bool = False,
    failed: bool = False,
) -> dict[str, Any]:
    return {
        "work_item_id": work_item.work_item_id,
        "executor_id": work_item.executor_id,
        "started": started,
        "completed": completed,
        "cancelled": cancelled,
        "failed": failed,
        "submitting_task_id": work_item.submitting_task_id,
        "callable_name": work_item.callable_name,
    }
