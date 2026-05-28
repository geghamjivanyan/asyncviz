"""Small ns ↔ s conversion helpers used across the runtime."""

from __future__ import annotations

NS_PER_SECOND = 1_000_000_000


def ns_to_seconds(ns: int) -> float:
    return ns / NS_PER_SECOND


def seconds_to_ns(seconds: float) -> int:
    return int(seconds * NS_PER_SECOND)
