from __future__ import annotations

import asyncio
import socket
import time
from contextlib import closing

import pytest

import asyncviz


def _reserve_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.integration
def test_start_with_instrumentation_patches_and_registers_tasks() -> None:
    port = _reserve_port()
    runtime = asyncviz.start(
        host="127.0.0.1",
        port=port,
        open_browser=False,
        enable_instrumentation=True,
    )
    try:
        registry = runtime.services.task_registry
        patcher = runtime.services.patcher
        assert patcher.is_patched

        # Create tasks from a USER-OWNED loop so the cross-thread publish path
        # is exercised. The dashboard's loop lives in a background thread.
        async def workload() -> int:
            async def _x() -> int:
                return 1

            tasks = [asyncio.create_task(_x()) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            return sum(results)

        total = asyncio.run(workload())
        assert total == 5

        # Give the bus dispatcher time to deliver events to the registry.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if registry.metrics_snapshot().completed_tasks >= 5:
                break
            time.sleep(0.02)

        snap = registry.metrics_snapshot()
        assert snap.total_tasks >= 5
        assert snap.completed_tasks >= 5
    finally:
        asyncviz.stop()
        assert not runtime.services.patcher.is_patched


@pytest.mark.integration
def test_stop_unpatches_create_task() -> None:
    port = _reserve_port()
    original = asyncio.create_task
    asyncviz.start(host="127.0.0.1", port=port, open_browser=False, enable_instrumentation=True)
    assert asyncio.create_task is not original
    asyncviz.stop()
    assert asyncio.create_task is original


@pytest.mark.integration
def test_disable_instrumentation_skips_patching() -> None:
    port = _reserve_port()
    original = asyncio.create_task
    runtime = asyncviz.start(
        host="127.0.0.1", port=port, open_browser=False, enable_instrumentation=False
    )
    try:
        assert asyncio.create_task is original
        assert not runtime.services.patcher.is_patched
    finally:
        asyncviz.stop()
