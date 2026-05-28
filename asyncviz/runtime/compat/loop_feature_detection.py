"""Runtime feature detection.

Probes the currently-installed event loop (or the loop policy when
no loop is running) and returns a frozen :class:`LoopCapabilities`.
Detection is *deterministic + side-effect-free*: it never installs
anything, never creates a new loop, never calls APIs that mutate
state. Two calls in identical conditions return identical results.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import sys
import time
from dataclasses import replace

from asyncviz.runtime.compat.models.loop_capabilities import (
    LoopCapabilities,
    asyncio_baseline_capabilities,
)
from asyncviz.runtime.compat.models.loop_kind import LoopKind


def is_uvloop_available() -> bool:
    """``True`` when uvloop is importable. Cheap — uses
    :func:`importlib.util.find_spec` so the module isn't loaded.
    """
    return importlib.util.find_spec("uvloop") is not None


def is_running_under_uvloop(loop: asyncio.AbstractEventLoop | None = None) -> bool:
    """``True`` when the supplied loop is a uvloop instance."""
    candidate = loop if loop is not None else _try_get_running_loop()
    if candidate is None:
        return False
    return _classify_loop(candidate) == LoopKind.UVLOOP


def detect_active_loop(
    loop: asyncio.AbstractEventLoop | None = None,
) -> LoopCapabilities:
    """Return capabilities of the active loop (or
    :func:`asyncio_baseline_capabilities` if nothing is running)."""
    candidate = loop if loop is not None else _try_get_running_loop()
    if candidate is None:
        return _capabilities_from_policy()
    return _capabilities_from_loop(candidate)


def _try_get_running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def _capabilities_from_policy() -> LoopCapabilities:
    """When no loop is running we inspect the active policy."""
    try:
        policy = asyncio.get_event_loop_policy()
    except Exception:
        return asyncio_baseline_capabilities()
    impl = type(policy).__module__
    if impl.startswith("uvloop"):
        return replace(
            asyncio_baseline_capabilities(),
            kind=LoopKind.UVLOOP,
            implementation=impl,
            version=_uvloop_version(),
        )
    return asyncio_baseline_capabilities()


def _capabilities_from_loop(loop: asyncio.AbstractEventLoop) -> LoopCapabilities:
    kind = _classify_loop(loop)
    implementation = type(loop).__module__
    version = _uvloop_version() if kind == LoopKind.UVLOOP else f"cpython={sys.version.split()[0]}"
    supports_task_factory = hasattr(loop, "set_task_factory")
    supports_call_soon_threadsafe = hasattr(loop, "call_soon_threadsafe")
    supports_create_task = hasattr(loop, "create_task")
    supports_run_in_executor = hasattr(loop, "run_in_executor")
    supports_set_debug = hasattr(loop, "set_debug")
    supports_get_clock_resolution = hasattr(loop, "get_clock_resolution")
    supports_create_unix_connection = hasattr(loop, "create_unix_connection")
    # uvloop ships ``add_signal_handler`` on POSIX but not Windows.
    supports_signal_handlers = hasattr(loop, "add_signal_handler") and sys.platform != "win32"

    monotonic_clock_resolution_ns = _probe_clock_resolution(loop)
    replay_safe = kind in (LoopKind.ASYNCIO, LoopKind.UVLOOP)

    return LoopCapabilities(
        kind=kind,
        implementation=implementation,
        version=version,
        supports_task_factory=supports_task_factory,
        supports_call_soon_threadsafe=supports_call_soon_threadsafe,
        supports_create_task=supports_create_task,
        supports_run_in_executor=supports_run_in_executor,
        supports_set_debug=supports_set_debug,
        supports_get_clock_resolution=supports_get_clock_resolution,
        supports_create_unix_connection=supports_create_unix_connection,
        supports_signal_handlers=supports_signal_handlers,
        monotonic_clock_resolution_ns=monotonic_clock_resolution_ns,
        replay_safe=replay_safe,
    )


def _classify_loop(loop: asyncio.AbstractEventLoop) -> LoopKind:
    impl = type(loop).__module__
    if impl.startswith("uvloop"):
        return LoopKind.UVLOOP
    if impl.startswith("anyio"):
        return LoopKind.ANYIO
    if impl.startswith("trio"):
        return LoopKind.TRIO
    if impl.startswith("asyncio"):
        return LoopKind.ASYNCIO
    return LoopKind.UNKNOWN


def _probe_clock_resolution(loop: asyncio.AbstractEventLoop) -> int:
    """Return the loop's monotonic-clock resolution in nanoseconds.

    Falls back to :func:`time.get_clock_info` when the loop refuses
    to disclose. Never raises.
    """
    getter = getattr(loop, "get_clock_resolution", None)
    if getter is not None:
        with contextlib.suppress(Exception):
            return int(getter() * 1e9)
    with contextlib.suppress(Exception):
        info = time.get_clock_info("monotonic")
        return int(info.resolution * 1e9)
    return 0


def _uvloop_version() -> str:
    try:
        import uvloop

        version = getattr(uvloop, "__version__", "unknown")
        return f"uvloop={version}"
    except Exception:
        return "uvloop=unknown"
