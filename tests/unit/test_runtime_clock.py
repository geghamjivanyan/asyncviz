from __future__ import annotations

import itertools
import json
import threading
import time
import uuid

import pytest

from asyncviz.runtime.clock import (
    ClockSnapshot,
    Duration,
    EventTimestamp,
    MonotonicTimestamp,
    RuntimeClock,
    RuntimeTimestamp,
    SequenceGenerator,
    get_runtime_clock,
    reset_runtime_clock,
    set_default_runtime_clock,
)
from asyncviz.runtime.clock.conversions import (
    ns_to_ms,
    ns_to_seconds,
    seconds_to_ns,
    wall_seconds_to_iso,
)
from asyncviz.runtime.clock.exceptions import ClockSequenceOverflowError
from asyncviz.runtime.clock.synchronization import (
    ClockSkewSample,
    estimate_skew,
)

# ── Duration ──────────────────────────────────────────────────────────────


def test_duration_clamps_negative_to_zero() -> None:
    d = Duration(nanoseconds=-5)
    assert d.nanoseconds == 0
    assert d.seconds == 0.0


def test_duration_seconds_and_milliseconds() -> None:
    d = Duration(nanoseconds=1_500_000_000)
    assert d.seconds == pytest.approx(1.5)
    assert d.milliseconds == pytest.approx(1500.0)


def test_duration_from_seconds_round_trip() -> None:
    d = Duration.from_seconds(2.25)
    assert d.nanoseconds == 2_250_000_000
    assert d.seconds == pytest.approx(2.25)


def test_duration_between_handles_reversed_inputs() -> None:
    # End before start ⇒ zero, never negative.
    d = Duration.between(start_ns=200, end_ns=100)
    assert d.nanoseconds == 0


# ── conversions ──────────────────────────────────────────────────────────


def test_conversions_round_trip_ns_seconds() -> None:
    assert ns_to_seconds(1_500_000_000) == pytest.approx(1.5)
    assert seconds_to_ns(1.5) == 1_500_000_000
    assert ns_to_ms(1_500_000_000) == pytest.approx(1500.0)


def test_wall_seconds_to_iso_emits_z_suffix() -> None:
    iso = wall_seconds_to_iso(0.0)
    assert iso == "1970-01-01T00:00:00Z"


# ── SequenceGenerator ────────────────────────────────────────────────────


def test_sequence_starts_at_one_and_is_strictly_increasing() -> None:
    seq = SequenceGenerator()
    values = [seq.next() for _ in range(10)]
    assert values == list(range(1, 11))
    assert seq.current == 10


def test_sequence_overflow_raises() -> None:
    seq = SequenceGenerator(start=0, max_value=3)
    [seq.next() for _ in range(3)]
    with pytest.raises(ClockSequenceOverflowError):
        seq.next()


def test_sequence_concurrent_allocation_is_unique_and_monotonic() -> None:
    """Stress: 16 threads x 5_000 allocations - each value unique & strictly ordered."""
    seq = SequenceGenerator()
    values: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        local = [seq.next() for _ in range(5_000)]
        with lock:
            values.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(values) == 16 * 5_000
    assert len(set(values)) == 16 * 5_000
    assert max(values) == 16 * 5_000
    assert min(values) == 1


# ── RuntimeClock — primitives ────────────────────────────────────────────


def test_runtime_clock_runtime_id_is_unique_and_stable() -> None:
    c1 = RuntimeClock()
    c2 = RuntimeClock()
    assert c1.runtime_id != c2.runtime_id
    assert c1.runtime_id == c1.runtime_id  # stable


def test_runtime_clock_started_at_is_close_to_wall_clock() -> None:
    before = time.time()
    clock = RuntimeClock()
    after = time.time()
    assert before <= clock.started_at <= after


def test_runtime_clock_monotonic_is_strictly_non_decreasing() -> None:
    clock = RuntimeClock()
    readings = [clock.monotonic_ns() for _ in range(10_000)]
    assert all(b >= a for a, b in itertools.pairwise(readings))


def test_runtime_clock_now_is_non_decreasing_across_calls() -> None:
    """``now()`` is drift-safe — it MUST never go backwards within one clock."""
    clock = RuntimeClock()
    readings = [clock.now() for _ in range(10_000)]
    assert all(b >= a for a, b in itertools.pairwise(readings))


def test_runtime_clock_uptime_grows_monotonically() -> None:
    clock = RuntimeClock()
    a = clock.runtime_uptime_ns()
    time.sleep(0.005)
    b = clock.runtime_uptime_ns()
    assert b > a
    # ``runtime_uptime()`` is sampled fractionally later than ``b`` was,
    # so it must be ≥ b/1e9 — not equal — and within a millisecond.
    seconds_later = clock.runtime_uptime()
    assert seconds_later >= b / 1_000_000_000
    assert seconds_later - b / 1_000_000_000 < 0.01


def test_runtime_clock_next_sequence_is_strictly_increasing() -> None:
    clock = RuntimeClock()
    seq = [clock.next_sequence() for _ in range(100)]
    assert seq == list(range(1, 101))
    assert clock.current_sequence == 100


# ── RuntimeClock — timestamp stamping ────────────────────────────────────


def test_timestamp_carries_full_triple() -> None:
    clock = RuntimeClock()
    ts = clock.timestamp()
    assert isinstance(ts, RuntimeTimestamp)
    assert ts.runtime_id == clock.runtime_id
    assert ts.monotonic_ns > 0
    assert ts.monotonic_seconds > 0
    assert ts.wall_seconds > 0
    assert ts.wall_iso.endswith("Z")


def test_timestamp_does_not_allocate_sequence() -> None:
    """``timestamp()`` is observation-only — it must NOT consume sequence ids."""
    clock = RuntimeClock()
    before = clock.current_sequence
    clock.timestamp()
    assert clock.current_sequence == before


def test_stamp_event_allocates_sequence_each_time() -> None:
    clock = RuntimeClock()
    a = clock.stamp_event()
    b = clock.stamp_event()
    assert isinstance(a, EventTimestamp)
    assert b.sequence == a.sequence + 1
    assert b.monotonic_ns >= a.monotonic_ns
    assert b.wall_seconds >= a.wall_seconds


def test_monotonic_timestamp_is_lightweight() -> None:
    clock = RuntimeClock()
    ts = clock.monotonic_timestamp()
    assert isinstance(ts, MonotonicTimestamp)
    assert ts.monotonic_ns > 0


def test_duration_since_ns_returns_non_negative_even_with_future_anchor() -> None:
    clock = RuntimeClock()
    future = clock.monotonic_ns() + 10_000_000_000  # 10s in the future
    d = clock.duration_since_ns(future)
    assert d.nanoseconds == 0


# ── RuntimeClock — observability ─────────────────────────────────────────


def test_clock_snapshot_round_trip_through_pydantic_json() -> None:
    clock = RuntimeClock()
    snap = clock.snapshot()
    assert isinstance(snap, ClockSnapshot)

    raw = snap.model_dump_json()
    rebuilt = ClockSnapshot.model_validate(json.loads(raw))
    assert rebuilt.runtime_id == clock.runtime_id
    assert rebuilt.uptime_ns >= 0
    assert rebuilt.current_sequence == clock.current_sequence


def test_metrics_snapshot_tracks_issuance() -> None:
    clock = RuntimeClock()
    clock.next_sequence()
    clock.next_sequence()
    clock.timestamp()
    metrics = clock.metrics_snapshot()
    assert metrics.sequence_issued == 2
    assert metrics.timestamps_issued >= 1
    assert metrics.uptime_seconds >= 0


# ── default clock plumbing ───────────────────────────────────────────────


def test_default_clock_is_lazy_and_idempotent() -> None:
    reset_runtime_clock()
    a = get_runtime_clock()
    b = get_runtime_clock()
    assert a is b


def test_set_default_runtime_clock_replaces_singleton() -> None:
    reset_runtime_clock()
    custom = RuntimeClock()
    set_default_runtime_clock(custom)
    assert get_runtime_clock() is custom
    reset_runtime_clock()


# ── RuntimeTimestamp serialization ───────────────────────────────────────


def test_runtime_timestamp_to_dict_is_json_safe() -> None:
    ts = RuntimeTimestamp(
        wall_seconds=1700000000.123,
        monotonic_ns=1_234_567_890,
        runtime_id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
    )
    d = ts.to_dict()
    # All fields are JSON-encodable primitives.
    json.dumps(d)
    assert d["wall_seconds"] == 1700000000.123
    assert d["monotonic_seconds"] == pytest.approx(1.23456789)
    assert d["monotonic_ns"] == 1_234_567_890
    assert d["runtime_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert d["wall_iso"].endswith("Z")


# ── synchronization placeholder ──────────────────────────────────────────


def test_clock_skew_sample_offset_helpers() -> None:
    sample = ClockSkewSample(
        local_runtime_id=uuid.uuid4(),
        remote_runtime_id=uuid.uuid4(),
        local_monotonic_ns=1_000_000_000,
        remote_monotonic_ns=2_500_000_000,
        offset_ns=1_500_000_000,
    )
    assert sample.offset_seconds == pytest.approx(1.5)


def test_estimate_skew_is_placeholder_returning_none() -> None:
    assert estimate_skew([]) is None
