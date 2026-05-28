from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.blocking.stack_capture import (
    CapturedFrame,
    CapturedStack,
    CapturedTaskMetadata,
    StackCaptureLimits,
)


def _frame(**overrides) -> CapturedFrame:
    base = {
        "filename": "/tmp/app.py",
        "module": "myapp",
        "function": "do_work",
        "lineno": 1,
        "code_context": None,
        "is_async": False,
        "is_internal": False,
    }
    base.update(overrides)
    return CapturedFrame(**base)


def test_captured_frame_to_dict_round_trips_all_fields() -> None:
    f = _frame(code_context="x = 1", is_async=True)
    d = f.to_dict()
    for key in (
        "filename",
        "module",
        "function",
        "lineno",
        "code_context",
        "is_async",
        "is_internal",
    ):
        assert key in d
    assert d["code_context"] == "x = 1"


def test_captured_stack_truncated_flag() -> None:
    """When frames_total > emitted + filtered, the stack is flagged truncated."""
    s = CapturedStack(
        capture_id=1,
        runtime_id="r",
        monotonic_ns=10,
        sample_index=0,
        window_id=None,
        severity="WARNING",
        trigger="violation",
        frames=(_frame(),),
        frames_total=10,
        filtered_count=2,
        thread_id=1,
    )
    # 10 raw - 2 filtered = 8 expected, but only 1 emitted → truncated
    assert s.truncated is True
    assert s.frame_count == 1


def test_captured_stack_to_dict_carries_task_block() -> None:
    s = CapturedStack(
        capture_id=1,
        runtime_id="r",
        monotonic_ns=10,
        sample_index=None,
        window_id=None,
        severity="NONE",
        trigger="manual",
        frames=(),
        frames_total=0,
        filtered_count=0,
        thread_id=1,
        task=CapturedTaskMetadata(task_id="t1"),
    )
    d = s.to_dict()
    assert d["task"]["task_id"] == "t1"
    assert d["frame_count"] == 0


def test_limits_rejects_zero_depth() -> None:
    with pytest.raises(ValueError, match="max_depth must be > 0"):
        StackCaptureLimits(max_depth=0)


def test_limits_rejects_zero_code_length() -> None:
    with pytest.raises(ValueError, match="max_code_length must be > 0"):
        StackCaptureLimits(max_code_length=0)


def test_limits_rejects_zero_payload_bytes() -> None:
    with pytest.raises(ValueError, match="max_payload_bytes must be > 0"):
        StackCaptureLimits(max_payload_bytes=0)


def test_limits_to_dict_round_trips() -> None:
    lim = StackCaptureLimits(max_depth=10, max_code_length=20, max_payload_bytes=30)
    d = lim.to_dict()
    assert d == {
        "max_depth": 10,
        "max_code_length": 20,
        "max_payload_bytes": 30,
        "capture_code_context": True,
    }
