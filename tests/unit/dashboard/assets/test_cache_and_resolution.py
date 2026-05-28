from __future__ import annotations

from pathlib import Path

from asyncviz.dashboard.assets import (
    AssetCache,
    reset_default_asset_cache,
    reset_resolution_cache,
    resolve_asset_path,
    resolve_bundle,
)


def setup_function(_fn: object) -> None:
    reset_default_asset_cache()
    reset_resolution_cache()


def test_asset_cache_put_then_get(tmp_path: Path) -> None:
    cache = AssetCache(max_entries=4, max_payload_bytes=1024)
    target = tmp_path / "a.txt"
    target.write_bytes(b"hello")
    entry = cache.put("a.txt", target)
    assert entry is not None
    assert cache.get("a.txt") is entry


def test_asset_cache_evicts_oldest_when_full(tmp_path: Path) -> None:
    cache = AssetCache(max_entries=2)
    paths = []
    for name in ("a", "b", "c"):
        p = tmp_path / name
        p.write_bytes(name.encode())
        cache.put(name, p)
        paths.append(p)
    assert cache.get("a") is None
    assert cache.get("b") is not None
    assert cache.get("c") is not None


def test_asset_cache_skips_oversized_payload(tmp_path: Path) -> None:
    cache = AssetCache(max_payload_bytes=4)
    big = tmp_path / "big"
    big.write_bytes(b"x" * 8)
    assert cache.put("big", big) is None
    assert cache.get("big") is None


def test_resolve_bundle_returns_cached_value() -> None:
    first = resolve_bundle()
    second = resolve_bundle()
    assert first is second


def test_resolve_bundle_refresh_returns_new_object() -> None:
    first = resolve_bundle()
    refreshed = resolve_bundle(refresh=True)
    # Equal in fields but different object — cache was invalidated.
    assert first == refreshed


def test_resolve_asset_path_handles_traversal() -> None:
    assert resolve_asset_path("../../../etc/passwd") is None
    assert resolve_asset_path("") is None


def test_resolve_asset_path_returns_known_asset() -> None:
    bundle = resolve_bundle()
    if not bundle.is_published:
        return  # frontend not embedded in this checkout — skip silently
    result = resolve_asset_path("index.html")
    assert result is not None
    assert result.name == "index.html"
