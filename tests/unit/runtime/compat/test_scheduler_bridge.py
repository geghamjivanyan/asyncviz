"""Scheduler-bridge tests."""

from __future__ import annotations

import asyncio

from asyncviz.runtime.compat import LoopSchedulerBridge


async def test_install_returns_true() -> None:
    bridge = LoopSchedulerBridge()
    loop = asyncio.get_running_loop()
    assert bridge.install(loop) is True
    bridge.restore()


async def test_records_call_soon() -> None:
    bridge = LoopSchedulerBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    try:
        future = loop.create_future()
        loop.call_soon(lambda: future.set_result(1))
        assert await future == 1
        assert bridge.stats().call_soon_count >= 1
    finally:
        bridge.restore()


async def test_records_call_later() -> None:
    bridge = LoopSchedulerBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    try:
        future = loop.create_future()
        loop.call_later(0.0, lambda: future.set_result(1))
        assert await future == 1
        assert bridge.stats().call_later_count >= 1
    finally:
        bridge.restore()


async def test_records_call_at() -> None:
    bridge = LoopSchedulerBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    try:
        future = loop.create_future()
        loop.call_at(loop.time() + 0.001, lambda: future.set_result(1))
        assert await future == 1
        assert bridge.stats().call_at_count >= 1
    finally:
        bridge.restore()


async def test_past_due_detection() -> None:
    bridge = LoopSchedulerBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    try:
        # call_later with negative delay → past-due.
        loop.call_later(-0.5, lambda: None)
        # call_at with a time in the past → past-due.
        loop.call_at(loop.time() - 1.0, lambda: None)
        await asyncio.sleep(0)
        assert bridge.stats().past_due_scheduled >= 2
    finally:
        bridge.restore()


async def test_restore_rolls_back_originals() -> None:
    bridge = LoopSchedulerBridge()
    loop = asyncio.get_running_loop()
    bridge.install(loop)
    assert bridge.stats().installed is True
    future = loop.create_future()
    loop.call_soon(lambda: future.set_result(None))
    await future
    assert bridge.stats().call_soon_count >= 1
    bridge.restore()
    assert bridge.stats().installed is False
    # After restore, future invocations must not increment the
    # bridge's counter.
    before = bridge.stats().call_soon_count
    future2 = loop.create_future()
    loop.call_soon(lambda: future2.set_result(None))
    await future2
    assert bridge.stats().call_soon_count == before
