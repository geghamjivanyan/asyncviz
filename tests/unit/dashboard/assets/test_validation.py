from __future__ import annotations

from pathlib import Path

from asyncviz.dashboard.assets import (
    FrontendAssetPublisher,
    NoopBuilder,
    load_manifest,
    validate_published_bundle,
    write_manifest,
)
from asyncviz.dashboard.assets.asset_manifest import build_manifest_model


def _publish(tmp_path: Path) -> Path:
    frontend = tmp_path / "frontend"
    dist = frontend / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>")
    (dist / "assets").mkdir()
    (dist / "assets" / "index-abc.js").write_text("x")
    (frontend / "package.json").write_text('{"version": "1.0.0"}')
    static = tmp_path / "static"
    publisher = FrontendAssetPublisher(
        repo_root=tmp_path,
        static_dir=static,
        frontend_dir=frontend,
        builder=NoopBuilder(),
    )
    publisher.publish(skip_build=True)
    return static


def test_validate_published_bundle_clean(tmp_path: Path) -> None:
    static = _publish(tmp_path)
    report = validate_published_bundle(static)
    assert report.ok
    assert report.file_count >= 2


def test_validate_detects_missing_file(tmp_path: Path) -> None:
    static = _publish(tmp_path)
    (static / "assets" / "index-abc.js").unlink()
    report = validate_published_bundle(static)
    assert not report.ok
    assert any(issue.code == "missing-asset" for issue in report.errors)


def test_validate_detects_hash_mismatch(tmp_path: Path) -> None:
    static = _publish(tmp_path)
    (static / "assets" / "index-abc.js").write_text("tampered")
    report = validate_published_bundle(static)
    assert not report.ok
    assert any(issue.code in {"hash-mismatch", "size-mismatch"} for issue in report.errors)


def test_validate_warns_when_no_manifest(tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html></html>")
    report = validate_published_bundle(static)
    assert any(issue.code == "missing-manifest" for issue in report.warnings)


def test_validate_handles_missing_required_files(tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()  # no index.html
    report = validate_published_bundle(static)
    assert not report.ok
    assert any(issue.code == "missing-required" for issue in report.errors)


def test_validate_rejects_newer_schema(tmp_path: Path) -> None:
    static = _publish(tmp_path)
    manifest = load_manifest(static)
    bumped = build_manifest_model(
        entries=manifest.entries,
        frontend_version=manifest.frontend_version,
        built_at_iso=manifest.built_at_iso,
        commit=manifest.commit,
    )
    # Force the schema version to the future.
    from dataclasses import replace

    bumped = replace(bumped, schema_version=999)
    write_manifest(static, bumped)
    report = validate_published_bundle(static)
    assert any(issue.code == "schema-too-new" for issue in report.errors)
