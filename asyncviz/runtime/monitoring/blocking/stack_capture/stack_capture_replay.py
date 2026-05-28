"""Replay helpers for the stack-capture engine.

Two flows:

* **Drive from the detector**: feed a sequence of
  :class:`DetectionOutcome` to the engine. Used by determinism tests
  and by future replay tools that drive the whole monitoring pipeline
  off a recorded lag-measurement log.

* **Decode from the event log**: parse a recorded
  ``runtime.monitoring.blocking.stack_capture`` event back into a
  :class:`CapturedStack`. Lets postmortem tooling reconstruct the
  capture without re-running the engine.

Replay-safe by design: the encoder (:class:`StackSerializer`) is a
deterministic function of the captured stack, and the decoder below
inverts the encoder field-for-field.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.monitoring.blocking.blocking_detector import DetectionOutcome
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_events import (
    BLOCKING_STACK_CAPTURE_EVENT_TYPE,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedFrame,
    CapturedStack,
    CapturedTaskMetadata,
)


def replay_into_engine(
    engine,  # BlockingStackCaptureEngine — avoid circular import
    outcomes: Iterable[DetectionOutcome],
) -> int:
    """Feed each outcome to the engine; return the number processed."""
    count = 0
    for outcome in outcomes:
        engine.on_detection(outcome)
        count += 1
    return count


def decode_stack_capture_event(event: RuntimeEvent) -> CapturedStack | None:
    """Inverse of :func:`build_stack_capture_event`.

    Returns ``None`` for any event that's not a stack-capture event or
    whose payload doesn't round-trip cleanly. The decoder never raises
    on a malformed payload — postmortem tooling should be allowed to
    skip un-decodable events rather than abort.
    """
    if event.event_type != BLOCKING_STACK_CAPTURE_EVENT_TYPE:
        return None
    payload = getattr(event, "payload", None)
    if not isinstance(payload, dict):
        return None
    return _decode_stack(payload)


def _decode_stack(payload: dict[str, Any]) -> CapturedStack | None:
    try:
        task_dict = payload.get("task") or {}
        if not isinstance(task_dict, dict):
            task_dict = {}
        task = CapturedTaskMetadata(
            task_id=task_dict.get("task_id"),
            task_name=task_dict.get("task_name"),
            coroutine_name=task_dict.get("coroutine_name"),
            parent_task_id=task_dict.get("parent_task_id"),
            root_task_id=task_dict.get("root_task_id"),
        )
        raw_frames = payload.get("frames") or []
        if not isinstance(raw_frames, list):
            # Malformed — refuse the whole decode rather than partially
            # populate. Postmortem tooling expects None for un-decodable
            # events.
            return None
        frames = tuple(
            CapturedFrame(
                filename=str(f.get("filename", "")),
                module=str(f.get("module", "")),
                function=str(f.get("function", "")),
                lineno=int(f.get("lineno", 0)),
                code_context=f.get("code_context"),
                is_async=bool(f.get("is_async", False)),
                is_internal=bool(f.get("is_internal", False)),
            )
            for f in raw_frames
            if isinstance(f, dict)
        )
        return CapturedStack(
            capture_id=int(payload.get("capture_id", 0)),
            runtime_id=str(payload.get("runtime_id", "")),
            monotonic_ns=int(payload.get("monotonic_ns", 0)),
            sample_index=payload.get("sample_index"),
            window_id=payload.get("window_id"),
            severity=str(payload.get("severity", "")),
            trigger=str(payload.get("trigger", "")),
            frames=frames,
            frames_total=int(payload.get("frames_total", len(frames))),
            filtered_count=int(payload.get("filtered_count", 0)),
            thread_id=int(payload.get("thread_id", 0)),
            task=task,
        )
    except (TypeError, ValueError, AttributeError):
        return None
