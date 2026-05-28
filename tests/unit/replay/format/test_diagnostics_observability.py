"""Format-layer diagnostics + tracing tests."""

from __future__ import annotations

from asyncviz.replay.format import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    ReplayFrame,
    build_format_diagnostics,
    clear_ndjson_trace,
    decode_frame,
    encode_frame,
    get_format_metrics_snapshot,
    get_ndjson_trace,
    is_ndjson_trace_enabled,
    set_ndjson_trace_enabled,
)


def _frame(seq: int) -> ReplayFrame:
    return ReplayFrame.for_runtime_event(
        sequence=seq,
        monotonic_ns=seq,
        payload_type="asyncio.task.created",
        payload={"task_id": f"t-{seq}"},
    )


def test_diagnostics_reports_active_versions() -> None:
    diag = build_format_diagnostics()
    assert diag.schema_version == SCHEMA_VERSION
    assert diag.protocol_version == PROTOCOL_VERSION


def test_diagnostics_includes_registered_payload_types() -> None:
    diag = build_format_diagnostics()
    assert "asyncio.task.created" in diag.registered_payload_types
    assert "snapshot.begin" in diag.registered_payload_types


def test_metrics_counted_for_encode_decode() -> None:
    frame = _frame(1)
    decode_frame(encode_frame(frame))
    snap = get_format_metrics_snapshot()
    assert snap.frames_encoded >= 1
    assert snap.frames_decoded >= 1


def test_trace_disabled_by_default_no_entries() -> None:
    assert not is_ndjson_trace_enabled()
    encode_frame(_frame(1))
    assert get_ndjson_trace() == ()


def test_trace_enabled_captures_entries() -> None:
    set_ndjson_trace_enabled(True)
    try:
        encode_frame(_frame(1))
        decode_frame(encode_frame(_frame(2)))
        entries = get_ndjson_trace()
        kinds = {e.kind for e in entries}
        assert "frame-encoded" in kinds
        assert "frame-decoded" in kinds
    finally:
        set_ndjson_trace_enabled(False)
        clear_ndjson_trace()
