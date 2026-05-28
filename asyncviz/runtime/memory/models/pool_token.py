"""Read-only snapshot of pool / interner statistics — used by the
diagnostics layer so callers don't have to import the singleton
metrics module."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PoolStatsSnapshot:
    name: str
    capacity: int
    size: int
    in_flight: int
    acquires: int
    releases: int
    pool_hits: int
    pool_misses: int
    double_releases: int

    @property
    def hit_ratio(self) -> float:
        attempts = self.pool_hits + self.pool_misses
        return self.pool_hits / attempts if attempts > 0 else 0.0
