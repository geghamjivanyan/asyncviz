from __future__ import annotations

import json
from pathlib import Path

from asyncviz.packaging.build_metadata import (
    BundleManifest,
    load_bundle_manifest,
)


def _write_bundle(tmp_path: Path, *, build_json: bool = False, vite: bool = False) -> Path:
    bundle = tmp_path / "static"
    bundle.mkdir()
    (bundle / "index.html").write_text("<html></html>")
    assets = bundle / "assets"
    assets.mkdir()
    (assets / "main-abc.js").write_text("console.log('x');")
    (assets / "main-abc.css").write_text("body{}")
    if build_json:
        (bundle / "build.json").write_text(
            json.dumps(
                {
                    "frontend_version": "1.2.3",
                    "build_id": "abc123",
                    "built_at": "2026-01-01T00:00:00Z",
                    "commit": "deadbeef",
                    "entries": [
                        {"file": "index.html", "role": "index"},
                        {"file": "assets/main-abc.js", "role": "entry"},
                        {"file": "assets/main-abc.css", "role": "asset"},
                    ],
                },
            ),
        )
    if vite:
        (bundle / ".vite").mkdir()
        (bundle / ".vite" / "manifest.json").write_text(
            json.dumps(
                {
                    "index.html": {
                        "file": "assets/main-abc.js",
                        "isEntry": True,
                    },
                    "src/foo.css": {
                        "file": "assets/main-abc.css",
                    },
                },
            ),
        )
    return bundle


def test_load_bundle_manifest_missing(tmp_path: Path) -> None:
    manifest = load_bundle_manifest(tmp_path / "does-not-exist")
    assert isinstance(manifest, BundleManifest)
    assert manifest.source == "missing"
    assert manifest.is_present is False


def test_load_bundle_manifest_scan(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    manifest = load_bundle_manifest(bundle)
    assert manifest.source == "scan"
    files = [entry.file for entry in manifest.entries]
    assert "index.html" in files
    assert "assets/main-abc.js" in files
    assert manifest.find("assets/main-abc.js") is not None


def test_load_bundle_manifest_prefers_build_json(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path, build_json=True)
    manifest = load_bundle_manifest(bundle)
    assert manifest.source == "build.json"
    assert manifest.frontend_version == "1.2.3"
    assert manifest.commit == "deadbeef"
    assert manifest.build_id == "abc123"


def test_load_bundle_manifest_falls_back_to_vite(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path, vite=True)
    manifest = load_bundle_manifest(bundle)
    assert manifest.source == "vite"
    files = [entry.file for entry in manifest.entries]
    assert "assets/main-abc.js" in files


def test_load_bundle_manifest_bad_json_falls_back_to_scan(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    (bundle / "build.json").write_text("not valid json")
    manifest = load_bundle_manifest(bundle)
    assert manifest.source == "scan"
