from __future__ import annotations

import threading
import time
import uuid

from asyncviz.runtime.clock.conversions import NS_PER_SECOND, wall_seconds_to_iso
from asyncviz.runtime.clock.models import ClockMetricsSnapshot, ClockSnapshot
from asyncviz.runtime.clock.sequence import SequenceGenerator
from asyncviz.runtime.clock.timestamps import (
    Duration,
    EventTimestamp,
    MonotonicTimestamp,
    RuntimeTimestamp,
)


class RuntimeClock:
    """Authoritative monotonic clock for an AsyncViz runtime.

    Owns the three timing primitives every other subsystem relies on:

    * **Monotonic time** — drift-immune, never goes backwards. Sourced from
      :func:`time.monotonic_ns` for nanosecond precision. Used for *all*
      duration math and event ordering.
    * **Wall-clock time** — derived from a single ``time.time()`` anchor
      captured at construction, plus the monotonic delta. This keeps
      wall-clock display monotonic *within the runtime* even if the system
      clock is stepped (NTP slew, manual change) after we start.
    * **Sequence** — globally-ordered 64-bit counter, the authoritative
      ordering primitive on the websocket wire and (eventually) the replay
      log. Allocated from a single :class:`SequenceGenerator`.

    A clock is identified by a ``runtime_id`` (uuid4 by default). Two
    timestamps with the same ``runtime_id`` are comparable; across
    ``runtime_id``\\ s only the sequence is comparable, and only via an
    external skew estimate (see :mod:`asyncviz.runtime.clock.synchronization`).

    Thread-safe. ``next_sequence`` / ``stamp_event`` / observability getters
    are safe from any thread; the cheap monotonic / wall readers are lockless
    because the kernel guarantees their atomicity.
    """

    def __init__(self, *, runtime_id: uuid.UUID | None = None) -> None:
        self._runtime_id = runtime_id or uuid.uuid4()
        self._wall_epoch_seconds = time.time()
        self._monotonic_epoch_ns = time.monotonic_ns()
        self._sequence = SequenceGenerator()
        self._lock = threading.Lock()
        self._timestamps_issued = 0

    # ── identity ─────────────────────────────────────────────────────────
    @property
    def runtime_id(self) -> uuid.UUID:
        return self._runtime_id

    @property
    def started_at(self) -> float:
        """Wall-clock seconds at clock construction. Stable for the lifetime."""
        return self._wall_epoch_seconds

    @property
    def started_at_monotonic_ns(self) -> int:
        return self._monotonic_epoch_ns

    # ── primitive readers ────────────────────────────────────────────────
    def monotonic_ns(self) -> int:
        """Raw nanosecond monotonic reading. Lockless; the canonical primitive."""
        return time.monotonic_ns()

    def monotonic(self) -> float:
        """Float-seconds monotonic reading. Drift-safe; *not* wall-clock."""
        return time.monotonic_ns() / NS_PER_SECOND

    def now(self) -> float:
        """Wall-clock seconds, derived monotonically from the runtime anchor.

        Guaranteed non-decreasing for the lifetime of the clock — even if the
        system wall clock is adjusted. The very first call effectively returns
        ``self._wall_epoch_seconds``; subsequent calls add the monotonic delta.
        """
        elapsed_ns = time.monotonic_ns() - self._monotonic_epoch_ns
        return self._wall_epoch_seconds + elapsed_ns / NS_PER_SECOND

    def now_iso(self) -> str:
        return wall_seconds_to_iso(self.now())

    def runtime_uptime_ns(self) -> int:
        return time.monotonic_ns() - self._monotonic_epoch_ns

    def runtime_uptime(self) -> float:
        """Float-seconds since clock construction. Strictly non-negative."""
        return self.runtime_uptime_ns() / NS_PER_SECOND

    # ── sequence ─────────────────────────────────────────────────────────
    def next_sequence(self) -> int:
        """Allocate the next ordering id. Globally increasing for this clock."""
        return self._sequence.next()

    @property
    def current_sequence(self) -> int:
        return self._sequence.current

    # ── stamping ─────────────────────────────────────────────────────────
    def timestamp(self) -> RuntimeTimestamp:
        """Capture a full :class:`RuntimeTimestamp` (no sequence allocation).

        Use this when a producer needs the triple but doesn't carry an
        ordering position (snapshots, /api responses). Sequence stays where
        it belongs — on envelopes flowing over /ws.
        """
        ns = time.monotonic_ns()
        wall = self._wall_epoch_seconds + (ns - self._monotonic_epoch_ns) / NS_PER_SECOND
        with self._lock:
            self._timestamps_issued += 1
        return RuntimeTimestamp(
            wall_seconds=wall,
            monotonic_ns=ns,
            runtime_id=self._runtime_id,
        )

    def monotonic_timestamp(self) -> MonotonicTimestamp:
        """Lightweight monotonic-only stamp. No wall-clock derivation, no lock."""
        return MonotonicTimestamp(monotonic_ns=time.monotonic_ns())

    def stamp_event(self) -> EventTimestamp:
        """Allocate a fresh ``(sequence, wall, monotonic)`` triple.

        Intended for the websocket bridge — it owns the wire-level ordering
        primitive and stamps every outbound runtime_event envelope here.
        """
        seq = self.next_sequence()
        ns = time.monotonic_ns()
        wall = self._wall_epoch_seconds + (ns - self._monotonic_epoch_ns) / NS_PER_SECOND
        with self._lock:
            self._timestamps_issued += 1
        return EventTimestamp(
            sequence=seq,
            wall_seconds=wall,
            monotonic_ns=ns,
            runtime_id=self._runtime_id,
        )

    def duration_since_ns(self, start_ns: int) -> Duration:
        """Duration from ``start_ns`` (a previous monotonic_ns reading) to now.

        Clamped to zero on the (extremely rare) case where the reading went
        backwards — keeps downstream display code from showing negatives.
        """
        return Duration.between(start_ns, time.monotonic_ns())

    # ── snapshots / observability ────────────────────────────────────────
    def snapshot(self) -> ClockSnapshot:
        ns = time.monotonic_ns()
        wall = self._wall_epoch_seconds + (ns - self._monotonic_epoch_ns) / NS_PER_SECOND
        uptime_ns = ns - self._monotonic_epoch_ns
        return ClockSnapshot(
            runtime_id=self._runtime_id,
            started_at_wall_seconds=self._wall_epoch_seconds,
            started_at_monotonic_ns=self._monotonic_epoch_ns,
            wall_now_seconds=wall,
            wall_now_iso=wall_seconds_to_iso(wall),
            monotonic_now_ns=ns,
            monotonic_now_seconds=ns / NS_PER_SECOND,
            uptime_seconds=uptime_ns / NS_PER_SECOND,
            uptime_ns=uptime_ns,
            current_sequence=self._sequence.current,
        )

    def metrics_snapshot(self) -> ClockMetricsSnapshot:
        with self._lock:
            issued = self._timestamps_issued
        return ClockMetricsSnapshot(
            runtime_id=self._runtime_id,
            sequence_issued=self._sequence.current,
            timestamps_issued=issued,
            uptime_seconds=self.runtime_uptime(),
        )


# ── module-level default clock (lazy singleton) ──────────────────────────
#
# Many existing call sites — chiefly Pydantic ``default_factory`` callables
# on the :class:`RuntimeEvent` envelope — need *some* clock without having
# one injected. The default exists for that purpose: it's lazily constructed
# on first access and reused thereafter. Bootstrap layers should call
# :func:`set_default_runtime_clock` early to bind the app's authoritative
# instance, so production code paths and the default both point to the same
# object.

_default_lock = threading.Lock()
_default_clock: RuntimeClock | None = None


def get_runtime_clock() -> RuntimeClock:
    """Return the process-wide default clock, constructing one if needed."""
    global _default_clock
    if _default_clock is None:
        with _default_lock:
            if _default_clock is None:
                _default_clock = RuntimeClock()
    return _default_clock


def set_default_runtime_clock(clock: RuntimeClock) -> None:
    """Bind ``clock`` as the process-wide default.

    Bootstrap calls this once with the app's authoritative clock so events
    constructed in user code (which goes through the default_factory) and
    events constructed by instrumentation share one ordering domain.
    """
    global _default_clock
    with _default_lock:
        _default_clock = clock


def reset_runtime_clock() -> None:
    """Forget the current default. Tests only.

    Safe to call from anywhere; the next ``get_runtime_clock()`` will lazily
    build a fresh instance.
    """
    global _default_clock
    with _default_lock:
        _default_clock = None
