"""Versioning + migration tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.format import (
    MIN_READABLE_SCHEMA_VERSION,
    SCHEMA_VERSION,
    MigrationKey,
    ReplayFrame,
    VersioningError,
    check_envelope_compatibility,
    decode_frame,
    encode_frame,
    get_format_metrics_snapshot,
    get_migration_registry,
    migrate_payload,
)


def test_envelope_compatibility_accepts_current_version() -> None:
    verdict = check_envelope_compatibility(SCHEMA_VERSION)
    assert verdict.compatible


def test_envelope_compatibility_tolerates_newer_versions() -> None:
    verdict = check_envelope_compatibility(SCHEMA_VERSION + 5)
    assert verdict.compatible
    assert "tolerated" in verdict.reason


def test_envelope_compatibility_rejects_too_old() -> None:
    verdict = check_envelope_compatibility(MIN_READABLE_SCHEMA_VERSION - 1)
    assert not verdict.compatible
    with pytest.raises(VersioningError):
        verdict.raise_if_incompatible()


def test_newer_envelope_decoding_records_skew_metric() -> None:
    line = encode_frame(
        ReplayFrame(
            schema_version=SCHEMA_VERSION + 1,
            frame_type="runtime_event",
            sequence=1,
            monotonic_ns=1,
            payload_type="asyncio.task.created",
            payload={"task_id": "t-1"},
        ),
    )
    decode_frame(line)
    snap = get_format_metrics_snapshot()
    assert snap.schema_skews_observed >= 1


def test_migration_registry_no_op_when_versions_match() -> None:
    frame = ReplayFrame.for_runtime_event(
        sequence=1, monotonic_ns=1, payload_type="x", payload={"a": 1},
    )
    out = migrate_payload(frame, from_version=2, to_version=2)
    assert out is frame


def test_migration_registry_applies_chain() -> None:
    registry = get_migration_registry()
    registry.register(
        MigrationKey(payload_type="custom", from_version=1, to_version=2),
        lambda data: {**data, "step2": True},
    )
    registry.register(
        MigrationKey(payload_type="custom", from_version=2, to_version=3),
        lambda data: {**data, "step3": True},
    )
    frame = ReplayFrame.for_runtime_event(
        sequence=1, monotonic_ns=1, payload_type="custom", payload={"original": True},
    )
    upgraded = migrate_payload(frame, from_version=1, to_version=3)
    assert upgraded.payload == {"original": True, "step2": True, "step3": True}
    snap = get_format_metrics_snapshot()
    assert snap.migrations_applied >= 1


def test_migration_registry_skips_missing_steps_additively() -> None:
    # No migrations registered; calling with a version jump should
    # be a no-op rather than an error.
    frame = ReplayFrame.for_runtime_event(
        sequence=1, monotonic_ns=1, payload_type="other", payload={"x": 1},
    )
    upgraded = migrate_payload(frame, from_version=1, to_version=5)
    assert upgraded.payload == {"x": 1}


def test_migration_registry_rejects_backwards_steps() -> None:
    registry = get_migration_registry()
    with pytest.raises(ValueError, match="must move forward"):
        registry.register(
            MigrationKey(payload_type="x", from_version=5, to_version=2),
            lambda data: data,
        )
