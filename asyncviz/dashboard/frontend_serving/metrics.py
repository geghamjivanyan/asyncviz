"""Self-observability counters for :class:`FrontendServingService`."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrontendServingMetricsSnapshot:
    """Immutable view of :class:`FrontendServingMetrics`."""

    asset_requests: int
    asset_hits: int
    asset_misses: int
    immutable_hits: int
    loose_hits: int
    index_served: int
    spa_fallbacks: int
    reserved_blocked: int
    path_traversal_blocked: int
    manifest_loads: int
    manifest_load_failures: int


class FrontendServingMetrics:
    """Thread-safe counters for the frontend serving layer.

    Tracks every request the service decides about: which assets hit,
    which missed, how many fell through to the SPA index, how many
    were blocked because they targeted a reserved backend prefix or
    attempted path traversal.

    Surfaced via :class:`FrontendServingMetricsSnapshot` on the
    ``/api/runtime/frontend/metrics`` debug endpoint and embedded in
    :class:`FrontendInfoResponse` so operators get one view.
    """

    __slots__ = (
        "_asset_hits",
        "_asset_misses",
        "_asset_requests",
        "_immutable_hits",
        "_index_served",
        "_lock",
        "_loose_hits",
        "_manifest_load_failures",
        "_manifest_loads",
        "_path_traversal_blocked",
        "_reserved_blocked",
        "_spa_fallbacks",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._asset_requests = 0
        self._asset_hits = 0
        self._asset_misses = 0
        self._immutable_hits = 0
        self._loose_hits = 0
        self._index_served = 0
        self._spa_fallbacks = 0
        self._reserved_blocked = 0
        self._path_traversal_blocked = 0
        self._manifest_loads = 0
        self._manifest_load_failures = 0

    def record_asset_request(self) -> None:
        with self._lock:
            self._asset_requests += 1

    def record_immutable_hit(self) -> None:
        with self._lock:
            self._asset_hits += 1
            self._immutable_hits += 1

    def record_loose_hit(self) -> None:
        with self._lock:
            self._asset_hits += 1
            self._loose_hits += 1

    def record_asset_miss(self) -> None:
        with self._lock:
            self._asset_misses += 1

    def record_index_served(self) -> None:
        with self._lock:
            self._index_served += 1

    def record_spa_fallback(self) -> None:
        with self._lock:
            self._spa_fallbacks += 1

    def record_reserved_blocked(self) -> None:
        with self._lock:
            self._reserved_blocked += 1

    def record_path_traversal_blocked(self) -> None:
        with self._lock:
            self._path_traversal_blocked += 1

    def record_manifest_load(self, *, failed: bool = False) -> None:
        with self._lock:
            if failed:
                self._manifest_load_failures += 1
            else:
                self._manifest_loads += 1

    def reset(self) -> None:
        with self._lock:
            self._asset_requests = 0
            self._asset_hits = 0
            self._asset_misses = 0
            self._immutable_hits = 0
            self._loose_hits = 0
            self._index_served = 0
            self._spa_fallbacks = 0
            self._reserved_blocked = 0
            self._path_traversal_blocked = 0
            self._manifest_loads = 0
            self._manifest_load_failures = 0

    def snapshot(self) -> FrontendServingMetricsSnapshot:
        with self._lock:
            return FrontendServingMetricsSnapshot(
                asset_requests=self._asset_requests,
                asset_hits=self._asset_hits,
                asset_misses=self._asset_misses,
                immutable_hits=self._immutable_hits,
                loose_hits=self._loose_hits,
                index_served=self._index_served,
                spa_fallbacks=self._spa_fallbacks,
                reserved_blocked=self._reserved_blocked,
                path_traversal_blocked=self._path_traversal_blocked,
                manifest_loads=self._manifest_loads,
                manifest_load_failures=self._manifest_load_failures,
            )
