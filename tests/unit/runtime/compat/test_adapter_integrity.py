"""Adapter + integrity tests."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from asyncviz.runtime.compat import (
    LoopAdapter,
    LoopIntegrityError,
    LoopKind,
    assert_compat_ok,
    asyncio_baseline_capabilities,
    check_capabilities,
    unknown_capabilities,
)


async def test_adapter_create_task_uses_loop() -> None:
    adapter = LoopAdapter(asyncio_baseline_capabilities())
    task = adapter.create_task(asyncio.sleep(0))
    await task
    assert adapter.stats().fallback_create_task == 0


async def test_adapter_falls_back_when_create_task_unsupported() -> None:
    caps = replace(asyncio_baseline_capabilities(), supports_create_task=False)
    adapter = LoopAdapter(caps)
    task = adapter.create_task(asyncio.sleep(0))
    await task
    assert adapter.stats().fallback_create_task == 1


async def test_adapter_call_soon_threadsafe_fallback() -> None:
    caps = replace(asyncio_baseline_capabilities(), supports_call_soon_threadsafe=False)
    adapter = LoopAdapter(caps)
    sentinel = []
    adapter.call_soon_threadsafe(lambda: sentinel.append("hit"))
    assert sentinel == ["hit"]
    assert adapter.stats().fallback_call_soon_threadsafe == 1


async def test_adapter_set_debug_fallback() -> None:
    caps = replace(asyncio_baseline_capabilities(), supports_set_debug=False)
    adapter = LoopAdapter(caps)
    assert adapter.set_debug(True) is False
    assert adapter.stats().fallback_set_debug == 1


def test_adapter_require_records_unavailable() -> None:
    caps = replace(asyncio_baseline_capabilities(), supports_signal_handlers=False)
    adapter = LoopAdapter(caps)
    assert adapter.require("supports_signal_handlers") is False
    assert adapter.stats().feature_unavailable == 1


def test_check_capabilities_passes_for_baseline() -> None:
    findings = check_capabilities(asyncio_baseline_capabilities())
    assert findings == ()


def test_check_capabilities_flags_unknown_loop() -> None:
    findings = check_capabilities(unknown_capabilities())
    kinds = {f.kind for f in findings}
    assert "unknown-loop" in kinds
    assert "missing-create-task" in kinds


def test_check_capabilities_flags_clock_resolution() -> None:
    caps = replace(asyncio_baseline_capabilities(), monotonic_clock_resolution_ns=2_000_000_000)
    findings = check_capabilities(caps, min_clock_resolution_ns=1_000_000_000)
    assert any(f.kind == "clock-resolution-degraded" for f in findings)


def test_check_capabilities_require_replay() -> None:
    caps = replace(asyncio_baseline_capabilities(), kind=LoopKind.UNKNOWN, replay_safe=False)
    findings = check_capabilities(caps, require_replay=True)
    assert any(f.kind == "replay-not-safe" for f in findings)


def test_assert_compat_ok_raises_on_findings() -> None:
    with pytest.raises(LoopIntegrityError):
        assert_compat_ok(unknown_capabilities())


def test_assert_compat_ok_passes_for_baseline() -> None:
    assert_compat_ok(asyncio_baseline_capabilities())
