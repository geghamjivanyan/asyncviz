"""Monkey-patch ``asyncio.Semaphore`` + ``asyncio.BoundedSemaphore`` to
emit AsyncViz events on every acquire / release.

Patching strategy:

* We do NOT subclass ``asyncio.Semaphore``. Replacing the original
  module attribute would still leave existing code using the
  unwrapped class. Instead we patch the methods on the original
  classes — every instance, past + future, picks up the
  instrumentation without recompiling user code.
* The patch records the originals on the engine; ``unpatch()``
  restores them atomically.
* Per-call recursion is guarded by a thread-local flag. CPython's
  ``Semaphore.acquire`` doesn't call back into ``release`` or
  ``acquire`` on the same instance, but the bus publisher might
  acquire OTHER semaphores while emitting events; the thread-local
  guard catches that exact case.
* ``release`` is patched on both ``Semaphore`` (the un-bounded version)
  and ``BoundedSemaphore`` (which overrides it to add the bound
  check). Both calls go through the same instrumentation engine.
* Every callback path swallows its own exceptions — a bug in the
  instrumentation can never break user semaphore semantics.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from asyncviz.instrumentation.semaphore.semaphore_configuration import (
    DEFAULT_SEMAPHORE_CONFIG,
    SemaphoreInstrumentationConfig,
)
from asyncviz.instrumentation.semaphore.semaphore_internal import is_semaphore_internal
from asyncviz.instrumentation.semaphore.semaphore_observability import (
    get_semaphore_metrics,
)
from asyncviz.instrumentation.semaphore.semaphore_registry import (
    SemaphoreRegistry,
    get_default_semaphore_registry,
)
from asyncviz.instrumentation.semaphore.semaphore_state import (
    read_initial_value,
    snapshot_semaphore,
)
from asyncviz.instrumentation.semaphore.semaphore_tracing import (
    record_semaphore_trace,
    set_semaphore_trace_enabled,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models.semaphore import (
    SemaphoreAcquiredEvent,
    SemaphoreAcquireStartedEvent,
    SemaphoreContentionDetectedEvent,
    SemaphoreCreatedEvent,
    SemaphoreReleasedEvent,
    SemaphoreWaitCancelledEvent,
)
from asyncviz.runtime.lineage import current_runtime_task
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.semaphore.patch")

# Re-entrancy guard so the instrumentation never publishes against
# itself (e.g. an event publisher that internally touches a semaphore
# would otherwise emit events from inside its own emit path).
_in_instrumentation = threading.local()


def _begin_instrumented() -> bool:
    if getattr(_in_instrumentation, "active", False):
        return False
    _in_instrumentation.active = True
    return True


def _end_instrumented() -> None:
    _in_instrumentation.active = False


# Task-local flag set during ``patched_acquire``'s ``await`` so a
# release on the SAME task (rare but possible — e.g. someone calling
# ``release`` from a finally inside acquire's wait callback) doesn't
# get double-attributed. We use a ContextVar — thread-locals would
# bleed across cooperating tasks on the same loop.
_in_outer_acquire: ContextVar[bool] = ContextVar(
    "_in_outer_acquire", default=False,
)

# Flag set while a patched ``__init__`` is running. ``BoundedSemaphore``
# overrides ``__init__`` to call ``super().__init__(value)`` — and the
# parent's ``__init__`` is *also* patched, so one BoundedSemaphore
# construction would fire two ``created`` events without this guard.
# Thread-local is fine here: ``__init__`` doesn't await, so no cross-
# task scheduling can clear the flag mid-construction.
_in_outer_init = threading.local()


def _begin_outer_init() -> bool:
    if getattr(_in_outer_init, "active", False):
        return False
    _in_outer_init.active = True
    return True


def _end_outer_init() -> None:
    _in_outer_init.active = False


PATCHED_CLASSES: tuple[type, ...] = (
    asyncio.Semaphore,
    asyncio.BoundedSemaphore,
)


class SemaphoreInstrumentationEngine:
    """Reversible, idempotent patcher for ``asyncio.Semaphore`` +
    ``asyncio.BoundedSemaphore``.

    Holds the original method references + the active engine state.
    Construct one per :func:`asyncviz.start` invocation so multiple
    runtimes don't fight over the global classes.
    """

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        registry: SemaphoreRegistry | None = None,
        config: SemaphoreInstrumentationConfig = DEFAULT_SEMAPHORE_CONFIG,
    ) -> None:
        self._bus = bus
        self._registry = registry or get_default_semaphore_registry()
        self._config = config
        self._lock = threading.Lock()
        self._patched = False
        # Per-class originals. ``BoundedSemaphore`` overrides ``release``
        # so we need separate originals for it vs. ``Semaphore``.
        self._originals: dict[type, dict[str, Callable[..., Any]]] = {}

    # ── public lifecycle ──────────────────────────────────────────

    @property
    def is_patched(self) -> bool:
        return self._patched

    @property
    def bus(self) -> EventBus | None:
        return self._bus

    @property
    def registry(self) -> SemaphoreRegistry:
        return self._registry

    @property
    def config(self) -> SemaphoreInstrumentationConfig:
        return self._config

    def set_bus(self, bus: EventBus | None) -> None:
        """Late-bind / unbind the event bus. Safe while patched."""
        self._bus = bus

    def patch(self) -> None:
        """Install the instrumented methods on ``asyncio.Semaphore``."""
        with self._lock:
            if self._patched:
                return
            engine = self

            for cls in PATCHED_CLASSES:
                # Snapshot originals BEFORE we replace anything on this
                # class. ``release`` on ``BoundedSemaphore`` is a
                # different function than on ``Semaphore`` — we must
                # restore each one to its own original.
                originals: dict[str, Callable[..., Any]] = {
                    "__init__": cls.__init__,
                    "acquire": cls.acquire,
                    "release": cls.release,
                }
                self._originals[cls] = originals

                original_init = originals["__init__"]
                original_acquire = originals["acquire"]
                original_release = originals["release"]

                def patched_init(
                    self_sem: asyncio.Semaphore,
                    *args,
                    _orig_init=original_init,
                    **kwargs,
                ):
                    is_outer = _begin_outer_init()
                    try:
                        _orig_init(self_sem, *args, **kwargs)
                    finally:
                        if is_outer:
                            _end_outer_init()
                    if not is_outer:
                        # Nested __init__ (e.g. BoundedSemaphore →
                        # super().__init__) — the outer call will fire
                        # the created event with the correct subclass.
                        return
                    if is_semaphore_internal(self_sem):
                        return
                    initial = read_initial_value(self_sem, *args, **kwargs)
                    engine._on_created(self_sem, initial)

                async def patched_acquire(
                    self_sem: asyncio.Semaphore,
                    _orig_acquire=original_acquire,
                ):
                    if is_semaphore_internal(self_sem):
                        return await _orig_acquire(self_sem)
                    # Determine "will block" BEFORE the await — read the
                    # raw permit count. ``locked()`` returns True when
                    # value <= 0; using it directly keeps us aligned with
                    # the stdlib's own definition.
                    will_block = bool(getattr(self_sem, "locked", lambda: False)())
                    engine._emit_acquire_started(self_sem, will_block=will_block)
                    if will_block:
                        engine._maybe_emit_contention(self_sem)
                    started = time.monotonic()
                    token = _in_outer_acquire.set(True)
                    try:
                        result = await _orig_acquire(self_sem)
                    except asyncio.CancelledError:
                        engine._emit_cancelled(self_sem, started)
                        raise
                    finally:
                        _in_outer_acquire.reset(token)
                    wait = (
                        max(0.0, time.monotonic() - started) if will_block else None
                    )
                    engine._emit_acquired(
                        self_sem, blocked=will_block, wait_seconds=wait,
                    )
                    return result

                def patched_release(
                    self_sem: asyncio.Semaphore,
                    _orig_release=original_release,
                ):
                    if is_semaphore_internal(self_sem):
                        return _orig_release(self_sem)
                    try:
                        return _orig_release(self_sem)
                    finally:
                        engine._emit_released(self_sem)

                cls.__init__ = patched_init  # type: ignore[method-assign]
                cls.acquire = patched_acquire  # type: ignore[method-assign]
                cls.release = patched_release  # type: ignore[method-assign]

            if self._config.trace_on_init:
                set_semaphore_trace_enabled(True)
            self._patched = True
            logger.debug("asyncio.Semaphore patched")

    def unpatch(self) -> None:
        """Restore the original methods. Idempotent."""
        with self._lock:
            if not self._patched:
                return
            for cls, originals in self._originals.items():
                for name, original in originals.items():
                    setattr(cls, name, original)
            self._originals.clear()
            self._patched = False
            logger.debug("asyncio.Semaphore unpatched")

    # ── internals ─────────────────────────────────────────────────

    def _safe_semaphore_id(
        self, semaphore: asyncio.Semaphore, *, initial_value: int | None = None,
    ) -> str:
        identity = self._registry.get(semaphore)
        if identity is not None:
            return identity.semaphore_id
        # Register lazily for semaphores constructed before the patch
        # attached or via paths we didn't intercept.
        return self._register(
            semaphore,
            initial_value=initial_value
            if initial_value is not None
            else int(getattr(semaphore, "_value", 1) or 1),
        ).semaphore_id

    def _register(
        self,
        semaphore: asyncio.Semaphore,
        *,
        initial_value: int,
    ) -> Any:
        creator = (
            current_runtime_task() if self._config.capture_creator_task_id else None
        )
        identity = self._registry.register(
            semaphore,
            initial_value=initial_value,
            creator_task_id=creator,
        )
        get_semaphore_metrics().record_registered()
        record_semaphore_trace("semaphore-registered", identity.semaphore_id)
        return identity

    def _on_created(self, semaphore: asyncio.Semaphore, initial_value: int) -> None:
        if not _begin_instrumented():
            get_semaphore_metrics().record_recursion_skip()
            record_semaphore_trace("recursion-skip", "semaphore-init")
            return
        try:
            identity = self._register(semaphore, initial_value=initial_value)
            if not self._config.emit_created:
                return
            self._publish(
                SemaphoreCreatedEvent(
                    semaphore_id=identity.semaphore_id,
                    semaphore_kind=identity.semaphore_kind,
                    initial_value=identity.initial_value,
                    bound_value=identity.bound_value,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(
                        snapshot_semaphore(
                            semaphore,
                            semaphore_id=identity.semaphore_id,
                            initial_value=identity.initial_value,
                            bound_value=identity.bound_value,
                        ),
                    ),
                    creator_task_id=identity.creator_task_id,
                    name=identity.name,
                ),
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("semaphore created instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_acquire_started(
        self, semaphore: asyncio.Semaphore, *, will_block: bool,
    ) -> None:
        if not self._config.emit_acquire:
            return
        if not _begin_instrumented():
            get_semaphore_metrics().record_recursion_skip()
            return
        try:
            sid = self._safe_semaphore_id(semaphore)
            identity = self._registry.get_by_id(sid)
            self._publish(
                SemaphoreAcquireStartedEvent(
                    semaphore_id=sid,
                    semaphore_kind=identity.semaphore_kind if identity else "unknown",
                    initial_value=identity.initial_value if identity else 0,
                    bound_value=identity.bound_value if identity else None,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(
                        snapshot_semaphore(
                            semaphore,
                            semaphore_id=sid,
                            initial_value=identity.initial_value if identity else 0,
                            bound_value=identity.bound_value if identity else None,
                        ),
                    ),
                    will_block=will_block,
                ),
            )
            record_semaphore_trace(
                "semaphore-acquire-started", f"{sid} will_block={will_block}",
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("semaphore acquire-started instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_acquired(
        self,
        semaphore: asyncio.Semaphore,
        *,
        blocked: bool,
        wait_seconds: float | None,
    ) -> None:
        if not self._config.emit_acquire:
            return
        if not _begin_instrumented():
            get_semaphore_metrics().record_recursion_skip()
            return
        try:
            sid = self._safe_semaphore_id(semaphore)
            identity = self._registry.get_by_id(sid)
            self._publish(
                SemaphoreAcquiredEvent(
                    semaphore_id=sid,
                    semaphore_kind=identity.semaphore_kind if identity else "unknown",
                    initial_value=identity.initial_value if identity else 0,
                    bound_value=identity.bound_value if identity else None,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(
                        snapshot_semaphore(
                            semaphore,
                            semaphore_id=sid,
                            initial_value=identity.initial_value if identity else 0,
                            bound_value=identity.bound_value if identity else None,
                        ),
                    ),
                    blocked=blocked,
                    wait_seconds=wait_seconds,
                ),
            )
            get_semaphore_metrics().record_acquire(blocked=blocked)
            record_semaphore_trace("semaphore-acquired", f"{sid} blocked={blocked}")
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("semaphore acquired instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_released(self, semaphore: asyncio.Semaphore) -> None:
        if not self._config.emit_release:
            return
        if not _begin_instrumented():
            return
        try:
            sid = self._safe_semaphore_id(semaphore)
            identity = self._registry.get_by_id(sid)
            self._publish(
                SemaphoreReleasedEvent(
                    semaphore_id=sid,
                    semaphore_kind=identity.semaphore_kind if identity else "unknown",
                    initial_value=identity.initial_value if identity else 0,
                    bound_value=identity.bound_value if identity else None,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(
                        snapshot_semaphore(
                            semaphore,
                            semaphore_id=sid,
                            initial_value=identity.initial_value if identity else 0,
                            bound_value=identity.bound_value if identity else None,
                        ),
                    ),
                ),
            )
            get_semaphore_metrics().record_release()
            record_semaphore_trace("semaphore-released", sid)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("semaphore released instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _emit_cancelled(
        self, semaphore: asyncio.Semaphore, started: float,
    ) -> None:
        if not self._config.emit_cancelled:
            return
        if not _begin_instrumented():
            return
        try:
            sid = self._safe_semaphore_id(semaphore)
            identity = self._registry.get_by_id(sid)
            wait = max(0.0, time.monotonic() - started)
            self._publish(
                SemaphoreWaitCancelledEvent(
                    semaphore_id=sid,
                    semaphore_kind=identity.semaphore_kind if identity else "unknown",
                    initial_value=identity.initial_value if identity else 0,
                    bound_value=identity.bound_value if identity else None,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(
                        snapshot_semaphore(
                            semaphore,
                            semaphore_id=sid,
                            initial_value=identity.initial_value if identity else 0,
                            bound_value=identity.bound_value if identity else None,
                        ),
                    ),
                    wait_seconds=wait,
                ),
            )
            get_semaphore_metrics().record_cancelled()
            record_semaphore_trace("semaphore-cancelled", sid)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("semaphore cancelled instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _maybe_emit_contention(self, semaphore: asyncio.Semaphore) -> None:
        if not self._config.emit_contention:
            return
        if not _begin_instrumented():
            return
        try:
            sid = self._safe_semaphore_id(semaphore)
            identity = self._registry.get_by_id(sid)
            snap = snapshot_semaphore(
                semaphore,
                semaphore_id=sid,
                initial_value=identity.initial_value if identity else 0,
                bound_value=identity.bound_value if identity else None,
            )
            # The new waiter that triggered this call hasn't been
            # registered in ``_waiters`` yet (CPython appends inside
            # ``acquire`` after the await begins). Count it explicitly
            # so the threshold transitions on the *current* attempt
            # rather than the next.
            effective_waiters = snap.waiter_count + 1
            if effective_waiters < self._config.contention_threshold:
                return
            if effective_waiters > self._config.contention_threshold:
                # Only fire on the leading edge — the patched_acquire
                # path can be entered repeatedly; we don't want to
                # spam events for every blocked acquire.
                return
            self._publish(
                SemaphoreContentionDetectedEvent(
                    semaphore_id=sid,
                    semaphore_kind=identity.semaphore_kind if identity else "unknown",
                    initial_value=identity.initial_value if identity else 0,
                    bound_value=identity.bound_value if identity else None,
                    task_id=current_runtime_task(),
                    snapshot=_snapshot_dict(snap),
                    waiter_count=effective_waiters,
                    current_value=snap.current_value,
                ),
            )
            get_semaphore_metrics().record_contention()
            record_semaphore_trace(
                "semaphore-contention", f"{sid} waiters={effective_waiters}",
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("semaphore contention instrumentation failed: %s", exc)
        finally:
            _end_instrumented()

    def _publish(self, event: Any) -> None:
        if self._bus is None:
            get_semaphore_metrics().record_dropped()
            record_semaphore_trace("event-dropped", "no bus")
            return
        try:
            self._bus.publish(event)
            get_semaphore_metrics().record_event()
        except Exception as exc:  # pragma: no cover — defensive
            get_semaphore_metrics().record_dropped()
            record_semaphore_trace("event-dropped", str(exc))


def _snapshot_dict(snap: Any) -> dict[str, Any]:
    return {
        "current_value": snap.current_value,
        "waiter_count": snap.waiter_count,
        "initial_value": snap.initial_value,
        "bound_value": snap.bound_value,
    }
