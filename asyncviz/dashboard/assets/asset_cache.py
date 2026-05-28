"""Tiny content cache for resolved asset payloads.

The dashboard serves a small handful of files (index.html + one or
two hashed bundles). Loading them off disk per request is fine for
correctness but wasteful — a bounded LRU keeps the hot ones in
memory without unbounded growth.

Cache reads aren't on a hot path in the v1 dashboard (the FastAPI
static handler already paths things off disk via OS page cache); the
cache is wired in here so a future replay viewer / standalone
dashboard can opt in.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CachedAsset:
    relative: str
    size_bytes: int
    payload: bytes


class AssetCache:
    """LRU asset-content cache.

    Default ``max_entries`` keeps the cache bounded; small assets
    stay; oversized binaries (> ``max_payload_bytes``) are skipped
    so we don't end up holding a 50 MB sourcemap in RAM forever.
    """

    def __init__(self, *, max_entries: int = 16, max_payload_bytes: int = 1 * 1024 * 1024) -> None:
        if max_entries < 1:
            raise ValueError(f"max_entries must be ≥ 1, got {max_entries}")
        self._max_entries = max_entries
        self._max_payload = max_payload_bytes
        self._items: OrderedDict[str, CachedAsset] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, relative: str) -> CachedAsset | None:
        with self._lock:
            cached = self._items.pop(relative, None)
            if cached is not None:
                self._items[relative] = cached  # mark as most-recently-used
            return cached

    def put(self, relative: str, path: Path) -> CachedAsset | None:
        """Read ``path`` into the cache (subject to size cap)."""
        try:
            payload = path.read_bytes()
        except OSError:
            return None
        if len(payload) > self._max_payload:
            return None
        cached = CachedAsset(relative=relative, size_bytes=len(payload), payload=payload)
        with self._lock:
            if relative in self._items:
                del self._items[relative]
            self._items[relative] = cached
            while len(self._items) > self._max_entries:
                self._items.popitem(last=False)
        return cached

    def invalidate(self, relative: str | None = None) -> None:
        with self._lock:
            if relative is None:
                self._items.clear()
            else:
                self._items.pop(relative, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


_default_cache = AssetCache()


def get_default_asset_cache() -> AssetCache:
    return _default_cache


def reset_default_asset_cache() -> None:
    global _default_cache
    _default_cache = AssetCache()
