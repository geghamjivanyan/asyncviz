"""Loop-feature adapter.

A thin abstraction over loop features the rest of the runtime
relies on. Each method calls the equivalent loop method when the
capability is present + routes through a documented fallback when
it isn't. The adapter records every fallback so diagnostics can
show which features are running on degraded paths.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from asyncviz.runtime.compat.models.loop_capabilities import LoopCapabilities

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AdapterStats:
    fallback_create_task: int
    fallback_call_soon_threadsafe: int
    fallback_run_in_executor: int
    fallback_set_debug: int
    feature_unavailable: int


class LoopAdapter:
    """Capability-aware façade over the active event loop."""

    __slots__ = (
        "_capabilities",
        "_fallback_call_soon_threadsafe",
        "_fallback_create_task",
        "_fallback_run_in_executor",
        "_fallback_set_debug",
        "_feature_unavailable",
        "_lock",
    )

    def __init__(self, capabilities: LoopCapabilities) -> None:
        self._capabilities = capabilities
        self._lock = threading.Lock()
        self._fallback_create_task = 0
        self._fallback_call_soon_threadsafe = 0
        self._fallback_run_in_executor = 0
        self._fallback_set_debug = 0
        self._feature_unavailable = 0

    @property
    def capabilities(self) -> LoopCapabilities:
        return self._capabilities

    def create_task(
        self,
        coro: Awaitable[T],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        name: str | None = None,
    ) -> asyncio.Task[T]:
        target = loop or asyncio.get_event_loop()
        if self._capabilities.supports_create_task:
            return target.create_task(coro, name=name)  # type: ignore[arg-type]
        with self._lock:
            self._fallback_create_task += 1
        return asyncio.ensure_future(coro, loop=target)  # type: ignore[arg-type]

    def call_soon_threadsafe(
        self,
        callback: Callable[..., Any],
        *args: Any,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> object:
        target = loop or asyncio.get_event_loop()
        if self._capabilities.supports_call_soon_threadsafe:
            return target.call_soon_threadsafe(callback, *args)
        with self._lock:
            self._fallback_call_soon_threadsafe += 1
        # Best-effort fallback — invoke synchronously. Loops that
        # lack threadsafe scheduling are rare + we don't pretend
        # to provide thread safety the loop itself doesn't.
        return callback(*args)

    def run_in_executor(
        self,
        executor: object,
        callback: Callable[..., T],
        *args: Any,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> Awaitable[T]:
        target = loop or asyncio.get_event_loop()
        if self._capabilities.supports_run_in_executor:
            return target.run_in_executor(executor, callback, *args)  # type: ignore[arg-type]
        with self._lock:
            self._fallback_run_in_executor += 1
        # Last-resort synchronous fallback: wrap the result in a
        # completed future. Same caveat as ``call_soon_threadsafe``.
        future: asyncio.Future[T] = target.create_future()
        try:
            future.set_result(callback(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def set_debug(self, value: bool, loop: asyncio.AbstractEventLoop | None = None) -> bool:
        target = loop or asyncio.get_event_loop()
        if self._capabilities.supports_set_debug:
            target.set_debug(value)
            return True
        with self._lock:
            self._fallback_set_debug += 1
        return False

    def require(self, feature: str) -> bool:
        """Hook for future capability checks. Returns ``True`` when
        the feature is supported; records a metric otherwise so the
        diagnostics page can flag gaps."""
        present = bool(getattr(self._capabilities, feature, False))
        if not present:
            with self._lock:
                self._feature_unavailable += 1
        return present

    def stats(self) -> AdapterStats:
        with self._lock:
            return AdapterStats(
                fallback_create_task=self._fallback_create_task,
                fallback_call_soon_threadsafe=self._fallback_call_soon_threadsafe,
                fallback_run_in_executor=self._fallback_run_in_executor,
                fallback_set_debug=self._fallback_set_debug,
                feature_unavailable=self._feature_unavailable,
            )

    def reset(self) -> None:
        with self._lock:
            self._fallback_create_task = 0
            self._fallback_call_soon_threadsafe = 0
            self._fallback_run_in_executor = 0
            self._fallback_set_debug = 0
            self._feature_unavailable = 0
