from __future__ import annotations

import json

from asyncviz.runtime.monitoring.blocking.stack_capture import (
    CapturedFrame,
    CapturedStack,
    StackCaptureLimits,
    StackSerializer,
)


def _stack(frame_count: int, code_context: str | None = None) -> CapturedStack:
    return CapturedStack(
        capture_id=1,
        runtime_id="r",
        monotonic_ns=10,
        sample_index=0,
        window_id=None,
        severity="CRITICAL",
        trigger="violation",
        frames=tuple(
            CapturedFrame(
                filename=f"/tmp/file{i}.py",
                module=f"app.mod{i}",
                function=f"fn{i}",
                lineno=i,
                code_context=code_context,
                is_async=False,
                is_internal=False,
            )
            for i in range(frame_count)
        ),
        frames_total=frame_count,
        filtered_count=0,
        thread_id=1,
    )


def test_serialize_small_stack_no_trim() -> None:
    s = StackSerializer(limits=StackCaptureLimits(max_payload_bytes=16 * 1024))
    out = s.serialize(_stack(3))
    assert out.trimmed is False
    assert out.original_frame_count == 3
    assert len(out.payload["frames"]) == 3
    assert out.json_bytes == len(json.dumps(out.payload, separators=(",", ":")).encode())


def test_serialize_trims_when_over_budget() -> None:
    # Big code-context fields per frame → easily exceed a tight budget.
    big = "x" * 200
    s = StackSerializer(limits=StackCaptureLimits(max_payload_bytes=1_500, max_code_length=400))
    out = s.serialize(_stack(20, code_context=big))
    assert out.trimmed is True
    assert out.original_frame_count == 20
    assert len(out.payload["frames"]) < 20
    assert out.json_bytes <= 1_500


def test_serialization_is_byte_identical_for_equal_stacks() -> None:
    s = StackSerializer(limits=StackCaptureLimits(max_payload_bytes=16 * 1024))
    out_a = s.serialize(_stack(5))
    out_b = s.serialize(_stack(5))
    assert out_a.payload == out_b.payload
    assert out_a.json_bytes == out_b.json_bytes


def test_payload_marked_truncated_when_trimmed() -> None:
    big = "y" * 250
    s = StackSerializer(limits=StackCaptureLimits(max_payload_bytes=800, max_code_length=400))
    out = s.serialize(_stack(10, code_context=big))
    assert out.trimmed is True
    assert out.payload["truncated"] is True


def test_serialization_payload_top_of_stack_preserved_during_trim() -> None:
    big = "z" * 250
    s = StackSerializer(limits=StackCaptureLimits(max_payload_bytes=800, max_code_length=400))
    stack = _stack(10, code_context=big)
    out = s.serialize(stack)
    # The first surviving frame must equal the original first frame.
    if out.payload["frames"]:
        assert out.payload["frames"][0]["function"] == stack.frames[0].function


def test_empty_stack_payload_remains_serializable() -> None:
    s = StackSerializer(limits=StackCaptureLimits(max_payload_bytes=200))
    out = s.serialize(_stack(0))
    assert out.payload["frames"] == []
    json.dumps(out.payload)  # must not raise
