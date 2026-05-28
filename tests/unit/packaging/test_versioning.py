from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

import asyncviz
from asyncviz.packaging import (
    PackageMetadata,
    get_package_metadata,
    package_version,
)


def test_package_version_matches_pyproject() -> None:
    pyproject = tomllib.loads(
        Path(__file__).resolve().parents[3].joinpath("pyproject.toml").read_text(encoding="utf-8"),
    )
    expected = pyproject["project"]["version"]
    assert package_version() == expected
    # The public ``asyncviz.__version__`` re-export must agree.
    assert asyncviz.__version__ == expected


def test_get_package_metadata_returns_bundle() -> None:
    meta = get_package_metadata()
    assert isinstance(meta, PackageMetadata)
    assert meta.name == "asyncviz"
    assert meta.version == package_version()
    assert meta.build_identity.version == meta.version
    assert meta.asset_resolution.bundle_dir.name == "static"


def test_build_identity_picks_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASYNCVIZ_BUILD_COMMIT", "f00ba2")
    monkeypatch.setenv("ASYNCVIZ_BUILD_TIMESTAMP", "2030-01-02T03:04:05Z")
    monkeypatch.setenv("ASYNCVIZ_BUILD_CHANNEL", "nightly")
    meta = get_package_metadata()
    assert meta.build_identity.commit == "f00ba2"
    assert meta.build_identity.timestamp == "2030-01-02T03:04:05Z"
    assert meta.build_identity.channel == "nightly"


def test_build_identity_reads_build_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Construct a fake bundle dir + monkey-patch the resolver.
    bundle = tmp_path / "static"
    bundle.mkdir()
    (bundle / "index.html").write_text("<html></html>")
    (bundle / "build.json").write_text(
        json.dumps(
            {
                "frontend_version": "9.9.9",
                "build_id": "build-id-xyz",
                "built_at": "2031-06-07T12:00:00Z",
                "commit": "shashah",
                "entries": [{"file": "index.html", "role": "index"}],
            },
        ),
    )

    from asyncviz.packaging import assets

    real_resolve = assets._resolve_bundle_dir
    monkeypatch.setattr(assets, "_resolve_bundle_dir", lambda: (bundle, "file-fallback"))
    try:
        # Clear env overrides so the manifest wins.
        monkeypatch.delenv("ASYNCVIZ_BUILD_COMMIT", raising=False)
        monkeypatch.delenv("ASYNCVIZ_BUILD_TIMESTAMP", raising=False)
        monkeypatch.delenv("ASYNCVIZ_BUILD_CHANNEL", raising=False)
        meta = get_package_metadata()
        assert meta.bundle_manifest.source == "build.json"
        assert meta.build_identity.commit == "shashah"
        assert meta.build_identity.timestamp == "2031-06-07T12:00:00Z"
        assert meta.build_identity.frontend_version == "9.9.9"
        assert meta.build_identity.frontend_build_id == "build-id-xyz"
    finally:
        monkeypatch.setattr(assets, "_resolve_bundle_dir", real_resolve)
