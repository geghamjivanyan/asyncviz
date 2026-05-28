from __future__ import annotations

import uuid

from asyncviz.runtime.warnings.blocking import (
    BLOCKING_WARNING_ACTIVE_EVENT_TYPE,
    BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
    BLOCKING_WARNING_EVENT_TYPES,
    BLOCKING_WARNING_EXPIRED_EVENT_TYPE,
    BLOCKING_WARNING_OPENED_EVENT_TYPE,
    BLOCKING_WARNING_RECOVERED_EVENT_TYPE,
    BlockingWarningGroupState,
    EscalationEntry,
    WarningGroupSnapshot,
    build_blocking_warning_event,
    build_payload,
    decode_blocking_warning_event,
    event_type_for_transition,
    is_blocking_warning_event,
)


def _snapshot(**overrides) -> WarningGroupSnapshot:
    defaults: dict = {
        "group_id": "g1",
        "warning_id": "g1",
        "runtime_id": "r",
        "window_id": "w1",
        "state": BlockingWarningGroupState.OPENED,
        "severity": "CRITICAL",
        "peak_severity": "CRITICAL",
        "first_seen_ns": 100,
        "last_seen_ns": 100,
        "recovered_ns": None,
        "expired_ns": None,
        "peak_lag_ns": 50_000_000,
        "last_lag_ns": 50_000_000,
        "violation_count": 1,
        "escalation_count": 0,
        "capture_ids": (),
        "escalation_history": (),
        "task_id": None,
        "task_name": None,
        "coroutine_name": None,
    }
    defaults.update(overrides)
    return WarningGroupSnapshot(**defaults)


# ── event type registry ─────────────────────────────────────────────────


def test_event_type_constants() -> None:
    assert BLOCKING_WARNING_OPENED_EVENT_TYPE in BLOCKING_WARNING_EVENT_TYPES
    assert BLOCKING_WARNING_ESCALATED_EVENT_TYPE in BLOCKING_WARNING_EVENT_TYPES
    assert BLOCKING_WARNING_ACTIVE_EVENT_TYPE in BLOCKING_WARNING_EVENT_TYPES
    assert BLOCKING_WARNING_RECOVERED_EVENT_TYPE in BLOCKING_WARNING_EVENT_TYPES
    assert BLOCKING_WARNING_EXPIRED_EVENT_TYPE in BLOCKING_WARNING_EVENT_TYPES
    assert len(BLOCKING_WARNING_EVENT_TYPES) == 5


def test_event_type_for_transition_map() -> None:
    assert event_type_for_transition("opened") == BLOCKING_WARNING_OPENED_EVENT_TYPE
    assert event_type_for_transition("escalated") == BLOCKING_WARNING_ESCALATED_EVENT_TYPE
    assert event_type_for_transition("active") == BLOCKING_WARNING_ACTIVE_EVENT_TYPE
    assert event_type_for_transition("recovered") == BLOCKING_WARNING_RECOVERED_EVENT_TYPE
    assert event_type_for_transition("expired") == BLOCKING_WARNING_EXPIRED_EVENT_TYPE


def test_is_blocking_warning_event_predicate() -> None:
    assert is_blocking_warning_event(BLOCKING_WARNING_OPENED_EVENT_TYPE) is True
    assert is_blocking_warning_event("runtime.task.created") is False


# ── payload ─────────────────────────────────────────────────────────────


def test_payload_carries_all_canonical_fields() -> None:
    snap = _snapshot()
    payload = build_payload(snapshot=snap, transition="opened", sequence=7)
    d = payload.to_dict()
    for key in (
        "warning_id",
        "group_id",
        "runtime_id",
        "window_id",
        "state",
        "severity",
        "peak_severity",
        "first_seen_ns",
        "last_seen_ns",
        "recovered_ns",
        "expired_ns",
        "freeze_duration_ns",
        "peak_lag_ns",
        "violation_count",
        "escalation_count",
        "capture_ids",
        "escalation_history",
        "task_id",
        "task_name",
        "coroutine_name",
        "transition",
        "sequence",
    ):
        assert key in d
    assert d["transition"] == "opened"
    assert d["sequence"] == 7


def test_payload_freeze_duration_ms_conversion() -> None:
    snap = _snapshot(first_seen_ns=0, last_seen_ns=2_500_000, recovered_ns=2_500_000)
    payload = build_payload(snapshot=snap, transition="recovered", sequence=1)
    assert payload.freeze_duration_ms == 2.5


def test_payload_history_includes_escalation_entries() -> None:
    snap = _snapshot(
        escalation_history=(
            EscalationEntry(
                from_severity="CRITICAL",
                to_severity="FREEZE",
                monotonic_ns=200,
                sample_index=1,
            ),
        )
    )
    payload = build_payload(snapshot=snap, transition="escalated", sequence=1)
    assert len(payload.escalation_history) == 1
    assert payload.escalation_history[0]["from_severity"] == "CRITICAL"


# ── event factory ──────────────────────────────────────────────────────


def test_build_event_uses_transition_event_type() -> None:
    snap = _snapshot()
    payload = build_payload(snapshot=snap, transition="opened", sequence=1)
    event = build_blocking_warning_event(payload=payload)
    assert event.event_type == BLOCKING_WARNING_OPENED_EVENT_TYPE
    assert event.payload["group_id"] == "g1"


def test_runtime_id_override_propagates() -> None:
    snap = _snapshot()
    payload = build_payload(snapshot=snap, transition="opened", sequence=1)
    rid = uuid.uuid4()
    event = build_blocking_warning_event(payload=payload, runtime_id=rid)
    assert event.runtime_id == rid


def test_decode_round_trips_payload() -> None:
    snap = _snapshot(
        capture_ids=(1, 2, 3),
        task_id="t1",
        task_name="task-1",
        coroutine_name="myapp.do_work",
    )
    payload = build_payload(snapshot=snap, transition="active", sequence=42)
    event = build_blocking_warning_event(payload=payload)
    decoded = decode_blocking_warning_event(event)
    assert decoded is not None
    assert decoded.warning_id == "g1"
    assert decoded.capture_ids == (1, 2, 3)
    assert decoded.task_id == "t1"
    assert decoded.sequence == 42


def test_decode_returns_none_for_other_event_types() -> None:
    from asyncviz.runtime.events.event import RuntimeEvent

    other = RuntimeEvent.of("runtime.task.created")
    assert decode_blocking_warning_event(other) is None
