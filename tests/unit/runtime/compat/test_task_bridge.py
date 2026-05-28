"""Task-bridge tests."""

from __future__ import annotations

import asyncio
import contextlib

from asyncviz.runtime.compat import LoopTaskBridge


async def _say_hi() -> str:
    return "hi"


async def _boom() -> None:
    raise RuntimeError("boom")


async def test_install_returns_true_on_default_loop() -> None:
    bridge = LoopTaskBridge()
    loop = asyncio.get_running_loop()
    assert bridge.install(loop) is True
    assert bridge.stats().installed is True
    bridge.restore()


async def test_install_is_idempotent() -> None:
    bridge = LoopTaskBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    assert bridge.install(loop) is True
    bridge.restore()


async def test_records_task_lifecycle_counters() -> None:
    bridge = LoopTaskBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    try:
        t = asyncio.create_task(_say_hi())
        await t
        await asyncio.sleep(0)  # let the done-callback fire
        stats = bridge.stats()
        assert stats.tasks_created >= 1
        assert stats.tasks_completed >= 1
    finally:
        bridge.restore()


async def test_records_failed_tasks() -> None:
    bridge = LoopTaskBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    try:
        t = asyncio.create_task(_boom())
        with contextlib.suppress(RuntimeError):
            await t
        await asyncio.sleep(0)
        stats = bridge.stats()
        assert stats.tasks_failed >= 1
    finally:
        bridge.restore()


async def test_records_cancelled_tasks() -> None:
    bridge = LoopTaskBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    try:
        t = asyncio.create_task(asyncio.sleep(60))
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
        await asyncio.sleep(0)
        stats = bridge.stats()
        assert stats.tasks_cancelled >= 1
    finally:
        bridge.restore()


async def test_restore_rolls_back_factory() -> None:
    bridge = LoopTaskBridge()
    loop = asyncio.get_running_loop()
    original = loop.get_task_factory()
    bridge.install(loop)
    assert loop.get_task_factory() is not original
    bridge.restore()
    assert loop.get_task_factory() is original


async def test_reset_clears_counters() -> None:
    bridge = LoopTaskBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    try:
        await asyncio.gather(*(asyncio.create_task(_say_hi()) for _ in range(3)))
        await asyncio.sleep(0)
        assert bridge.stats().tasks_completed >= 3
        bridge.reset()
        assert bridge.stats().tasks_completed == 0
    finally:
        bridge.restore()
