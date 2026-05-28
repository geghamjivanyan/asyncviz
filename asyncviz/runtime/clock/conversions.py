from __future__ import annotations

from datetime import UTC, datetime

#: One nanosecond, in seconds.
NS_PER_SECOND: int = 1_000_000_000
#: One millisecond, in nanoseconds.
NS_PER_MS: int = 1_000_000
#: One microsecond, in nanoseconds.
NS_PER_US: int = 1_000


def ns_to_seconds(ns: int) -> float:
    """Nanoseconds → float seconds. Lossy past ~52 bits but fine for display."""
    return ns / NS_PER_SECOND


def seconds_to_ns(seconds: float) -> int:
    """Float seconds → integer nanoseconds. Rounds to nearest; never raises."""
    return round(seconds * NS_PER_SECOND)


def ns_to_ms(ns: int) -> float:
    """Nanoseconds → float milliseconds."""
    return ns / NS_PER_MS


def ns_to_us(ns: int) -> float:
    """Nanoseconds → float microseconds."""
    return ns / NS_PER_US


def wall_seconds_to_iso(wall_seconds: float) -> str:
    """Wall-clock UNIX seconds → RFC 3339 / ISO 8601 timestamp (UTC, ``Z``).

    This is the canonical wall-clock string format on the wire. Display layers
    (UI, logs) should never re-derive this from raw seconds — call here so
    everyone agrees on precision and zone.
    """
    return datetime.fromtimestamp(wall_seconds, tz=UTC).isoformat().replace("+00:00", "Z")
