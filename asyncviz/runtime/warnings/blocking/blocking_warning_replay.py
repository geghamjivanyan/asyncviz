"""Replay helpers for the blocking warning emitter.

Two flows:

* **Drive the emitter** from a sequence of ``DetectionOutcome`` +
  ``CapturedStack`` inputs. Used by determinism tests and by future
  replay tools that re-run the warning pipeline off a recorded log.
* **Decode an emitted event** back into a :class:`BlockingWarningPayload`.
  Lets postmortem tooling reconstruct group state without re-running
  the emitter.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.monitoring.blocking import CapturedStack, DetectionOutcome
from asyncviz.runtime.warnings.blocking.blocking_warning_events import (
    is_blocking_warning_event,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_payloads import (
    BlockingWarningPayload,
)


def replay_into_emitter(
    emitter,  # BlockingWarningEmitter — avoid circular import
    inputs: Iterable[DetectionOutcome | CapturedStack],
) -> int:
    """Drive the emitter through a recorded sequence of inputs.

    ``inputs`` may interleave :class:`DetectionOutcome` and
    :class:`CapturedStack` objects in the order they were originally
    produced; the emitter dispatches each to the right handler.

    Returns the total number of inputs processed.
    """
    count = 0
    for item in inputs:
        if isinstance(item, CapturedStack):
            emitter.on_capture(item)
        else:
            emitter.on_detection(item)
        count += 1
    return count


def decode_blocking_warning_event(event: RuntimeEvent) -> BlockingWarningPayload | None:
    """Inverse of :func:`build_blocking_warning_event`.

    Returns ``None`` for events that aren't blocking-warning events or
    whose payload can't be coerced cleanly. Postmortem tools should be
    able to skip un-decodable events rather than abort.
    """
    if not is_blocking_warning_event(event.event_type):
        return None
    payload = getattr(event, "payload", None)
    if not isinstance(payload, dict):
        return None
    return _decode_payload(payload)


def _decode_payload(payload: dict[str, Any]) -> BlockingWarningPayload | None:
    try:
        capture_ids = payload.get("capture_ids") or []
        if not isinstance(capture_ids, list):
            return None
        escalation_history = payload.get("escalation_history") or []
        if not isinstance(escalation_history, list):
            return None
        return BlockingWarningPayload(
            warning_id=str(payload.get("warning_id", "")),
            group_id=str(payload.get("group_id", "")),
            runtime_id=str(payload.get("runtime_id", "")),
            window_id=payload.get("window_id"),
            state=str(payload.get("state", "")),
            severity=str(payload.get("severity", "")),
            peak_severity=str(payload.get("peak_severity", payload.get("severity", ""))),
            first_seen_ns=int(payload.get("first_seen_ns", 0)),
            last_seen_ns=int(payload.get("last_seen_ns", 0)),
            recovered_ns=payload.get("recovered_ns"),
            expired_ns=payload.get("expired_ns"),
            freeze_duration_ns=int(payload.get("freeze_duration_ns", 0)),
            peak_lag_ns=int(payload.get("peak_lag_ns", 0)),
            last_lag_ns=int(payload.get("last_lag_ns", 0)),
            violation_count=int(payload.get("violation_count", 0)),
            escalation_count=int(payload.get("escalation_count", 0)),
            capture_ids=tuple(int(c) for c in capture_ids),
            escalation_history=tuple(e for e in escalation_history if isinstance(e, dict)),
            task_id=payload.get("task_id"),
            task_name=payload.get("task_name"),
            coroutine_name=payload.get("coroutine_name"),
            transition=str(payload.get("transition", "")),
            sequence=int(payload.get("sequence", 0)),
        )
    except (TypeError, ValueError, AttributeError):
        return None
