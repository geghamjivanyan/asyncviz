from __future__ import annotations

import json
from pathlib import Path

from asyncviz.dashboard.assets.asset_manifest import (
    build_manifest_model,
    load_manifest,
    write_manifest,
)
from asyncviz.dashboard.assets.asset_metadata import AssetManifestModel
from asyncviz.dashboard.assets.asset_registry import collect_assets


def _build_static(tmp_path: Path) -> Path:
    root = tmp_path / "static"
    root.mkdir()
    (root / "index.html").write_text("<html></html>")
    assets = root / "assets"
    assets.mkdir()
    (assets / "index-abc.js").write_text("console.log('x');")
    (assets / "index-abc.css").write_text("body{}")
    (assets / ".DS_Store").write_text("noise")  # should be ignored
    return root


def test_collect_assets_walks_tree_and_assigns_roles(tmp_path: Path) -> None:
    root = _build_static(tmp_path)
    entries = collect_assets(root)
    by_file = {entry.file: entry for entry in entries}
    assert "index.html" in by_file
    assert by_file["index.html"].role == "index"
    assert "assets/index-abc.js" in by_file
    assert by_file["assets/index-abc.js"].role == "entry"
    assert by_file["assets/index-abc.css"].role == "asset"
    # Ignored noise stays out.
    assert all(".DS_Store" not in entry.file for entry in entries)


def test_collect_assets_returns_sorted_for_determinism(tmp_path: Path) -> None:
    root = _build_static(tmp_path)
    entries = collect_assets(root)
    assert [e.file for e in entries] == sorted(e.file for e in entries)


def test_collect_assets_empty_for_missing_dir(tmp_path: Path) -> None:
    assert collect_assets(tmp_path / "missing") == ()


def test_manifest_round_trip(tmp_path: Path) -> None:
    root = _build_static(tmp_path)
    entries = collect_assets(root)
    manifest = build_manifest_model(
        entries=entries,
        frontend_version="1.2.3",
        built_at_iso="2026-01-01T00:00:00+00:00",
        commit="abc123",
    )
    path = write_manifest(root, manifest)
    assert path.is_file()
    loaded = load_manifest(root)
    assert loaded.schema_version == manifest.schema_version
    assert loaded.frontend_version == "1.2.3"
    assert loaded.total_files == len(entries)
    assert loaded.find("index.html") is not None


def test_manifest_to_dict_is_json_safe(tmp_path: Path) -> None:
    root = _build_static(tmp_path)
    manifest = build_manifest_model(
        entries=collect_assets(root),
        frontend_version="0.0.1",
        built_at_iso="2026-01-01T00:00:00+00:00",
        commit=None,
    )
    write_manifest(root, manifest)
    raw = json.loads((root / "build.json").read_text())
    assert raw["schema_version"] == 1
    assert raw["entries"][0]["file"] == "assets/index-abc.css"  # sorted
    assert "sha256" in raw["entries"][0]


def test_build_manifest_uses_unique_bundle_ids() -> None:
    a = build_manifest_model(
        entries=(), frontend_version="x", built_at_iso="t", commit=None,
    )
    b = build_manifest_model(
        entries=(), frontend_version="x", built_at_iso="t", commit=None,
    )
    assert a.bundle_id != b.bundle_id
    assert isinstance(a, AssetManifestModel)
