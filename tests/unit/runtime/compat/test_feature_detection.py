"""Feature detection tests."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.compat import (
    LoopKind,
    asyncio_baseline_capabilities,
    detect_active_loop,
    is_running_under_uvloop,
    is_uvloop_available,
)


def test_uvloop_available_returns_bool() -> None:
    assert isinstance(is_uvloop_available(), bool)


def test_detect_returns_capabilities_without_running_loop() -> None:
    caps = detect_active_loop()
    assert caps.kind in (LoopKind.ASYNCIO, LoopKind.UVLOOP, LoopKind.UNKNOWN)
    assert isinstance(caps.implementation, str)
    assert isinstance(caps.version, str)


async def test_detect_active_loop_inside_asyncio_loop() -> None:
    caps = detect_active_loop()
    assert caps.supports_create_task is True
    assert caps.supports_call_soon_threadsafe is True


async def test_is_running_under_uvloop_false_for_default_asyncio() -> None:
    # The pytest-asyncio runner uses the default policy.
    loop = asyncio.get_running_loop()
    if type(loop).__module__.startswith("uvloop"):
        pytest.skip("running under uvloop")
    assert is_running_under_uvloop(loop) is False


def test_baseline_capabilities_are_complete() -> None:
    caps = asyncio_baseline_capabilities()
    assert caps.kind == LoopKind.ASYNCIO
    assert caps.supports_create_task is True
    assert caps.supports_task_factory is True
    assert caps.replay_safe is True
