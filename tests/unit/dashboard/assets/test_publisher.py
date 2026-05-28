from __future__ import annotations

from pathlib import Path

from asyncviz.dashboard.assets import (
    FrontendAssetPublisher,
    NoopBuilder,
    PublishResult,
    load_manifest,
    reset_asset_metrics,
    reset_resolution_cache,
)


def _seed_frontend(tmp_path: Path) -> Path:
    frontend = tmp_path / "frontend"
    dist = frontend / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "index-abc.js").write_text("console.log('hi');")
    (assets / "index-abc.css").write_text("body{}")
    (frontend / "package.json").write_text('{"version": "9.9.9"}')
    return frontend


def setup_function(_fn: object) -> None:
    reset_asset_metrics()
    reset_resolution_cache()


def test_publisher_emits_manifest_and_copies(tmp_path: Path) -> None:
    frontend = _seed_frontend(tmp_path)
    static = tmp_path / "asyncviz" / "dashboard" / "static"
    publisher = FrontendAssetPublisher(
        repo_root=tmp_path,
        static_dir=static,
        frontend_dir=frontend,
        builder=NoopBuilder(),
    )
    result = publisher.publish(skip_build=True)
    assert isinstance(result, PublishResult)
    assert result.success
    assert result.files_copied == 3  # index + 2 assets
    assert (static / "index.html").is_file()
    assert (static / "build.json").is_file()
    manifest = load_manifest(static)
    assert manifest.frontend_version == "9.9.9"
    assert manifest.total_files == 3


def test_publisher_clean_removes_previous_embed(tmp_path: Path) -> None:
    frontend = _seed_frontend(tmp_path)
    static = tmp_path / "static"
    static.mkdir()
    (static / "obsolete.txt").write_text("delete me")
    publisher = FrontendAssetPublisher(
        repo_root=tmp_path,
        static_dir=static,
        frontend_dir=frontend,
        builder=NoopBuilder(),
    )
    result = publisher.publish(skip_build=True)
    assert result.files_removed == 1
    assert not (static / "obsolete.txt").exists()


def test_publisher_skip_clean_keeps_previous(tmp_path: Path) -> None:
    frontend = _seed_frontend(tmp_path)
    static = tmp_path / "static"
    static.mkdir()
    (static / "obsolete.txt").write_text("keep me")
    publisher = FrontendAssetPublisher(
        repo_root=tmp_path,
        static_dir=static,
        frontend_dir=frontend,
        builder=NoopBuilder(),
    )
    publisher.publish(skip_build=True, skip_clean=True)
    assert (static / "obsolete.txt").exists()


def test_publisher_dry_run_writes_nothing(tmp_path: Path) -> None:
    frontend = _seed_frontend(tmp_path)
    static = tmp_path / "static"
    publisher = FrontendAssetPublisher(
        repo_root=tmp_path,
        static_dir=static,
        frontend_dir=frontend,
        builder=NoopBuilder(),
    )
    result = publisher.publish(skip_build=True, dry_run=True)
    assert result.success
    assert result.files_copied == 0
    assert not static.exists()
    assert result.manifest is not None


def test_publisher_fails_when_dist_missing(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    publisher = FrontendAssetPublisher(
        repo_root=tmp_path,
        static_dir=tmp_path / "static",
        frontend_dir=frontend,
        builder=NoopBuilder(),
    )
    result = publisher.publish(skip_build=True)
    assert not result.success
    assert any("dist/index.html" in note for note in result.notes)
