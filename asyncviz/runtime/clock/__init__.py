"""Canonical runtime clock + timing primitives.

Public surface:

* :class:`RuntimeClock` — the authoritative monotonic clock object. One per
  AsyncViz runtime; exposed by bootstrap as ``app.state.runtime_clock``.
* :class:`RuntimeTimestamp` / :class:`MonotonicTimestamp` / :class:`EventTimestamp`
  — typed timestamp values; replay-safe, JSON-safe, frontend-friendly.
* :class:`Duration` — non-negative interval; the canonical duration type.
* :class:`SequenceGenerator` — 64-bit ordering primitive; the WS bridge
  delegates here.
* :class:`ClockSnapshot` / :class:`ClockMetricsSnapshot` — observability
  surfaces. Returned by ``/api/runtime/clock``.

The module also exposes a lazy default clock (``get_runtime_clock`` /
``set_default_runtime_clock`` / ``reset_runtime_clock``) so existing event
``default_factory`` hooks can centralize timing without explicit injection.
"""

from asyncviz.runtime.clock.clock import (
    RuntimeClock,
    get_runtime_clock,
    reset_runtime_clock,
    set_default_runtime_clock,
)
from asyncviz.runtime.clock.exceptions import (
    ClockError,
    ClockSequenceOverflowError,
    ClockSkewError,
)
from asyncviz.runtime.clock.models import ClockMetricsSnapshot, ClockSnapshot
from asyncviz.runtime.clock.sequence import MAX_SEQUENCE, SequenceGenerator
from asyncviz.runtime.clock.synchronization import (
    ClockSkewEstimate,
    ClockSkewSample,
    estimate_skew,
)
from asyncviz.runtime.clock.timestamps import (
    Duration,
    EventTimestamp,
    MonotonicTimestamp,
    RuntimeTimestamp,
)

__all__ = [
    "MAX_SEQUENCE",
    "ClockError",
    "ClockMetricsSnapshot",
    "ClockSequenceOverflowError",
    "ClockSkewError",
    "ClockSkewEstimate",
    "ClockSkewSample",
    "ClockSnapshot",
    "Duration",
    "EventTimestamp",
    "MonotonicTimestamp",
    "RuntimeClock",
    "RuntimeTimestamp",
    "SequenceGenerator",
    "estimate_skew",
    "get_runtime_clock",
    "reset_runtime_clock",
    "set_default_runtime_clock",
]
