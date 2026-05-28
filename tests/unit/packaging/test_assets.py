from __future__ import annotations

from pathlib import Path

import pytest

from asyncviz.packaging import (
    bundle_files,
    locate_frontend_bundle,
    resolve_frontend_asset,
)
from asyncviz.packaging.assets import (
    EditableInstall,
    PackagedInstall,
    UnknownInstall,
    _classify_install,
    _required_missing,
)


def test_locate_frontend_bundle_returns_resolution() -> None:
    res = locate_frontend_bundle()
    assert res.bundle_dir.name == "static"
    assert res.index_path.name == "index.html"
    assert res.assets_dir.name == "assets"
    # The shape detection must produce *one* of the three tagged-union
    # variants; the rest of the codebase pattern-matches against the
    # ``kind`` literal.
    assert res.install_shape.kind in {"editable", "packaged", "unknown"}
    assert res.resolved_via in {"importlib.resources", "file-fallback"}


def test_resolve_frontend_asset_handles_traversal(tmp_path: Path) -> None:
    # ``..`` must never escape the bundle root.
    assert resolve_frontend_asset("../etc/passwd") is None
    assert resolve_frontend_asset("") is None


def test_resolve_frontend_asset_returns_path_when_present() -> None:
    res = locate_frontend_bundle()
    if not res.is_embedded:
        pytest.skip("frontend not embedded; cannot verify resolution against real file")
    resolved = resolve_frontend_asset("index.html")
    assert resolved is not None
    assert resolved.is_file()


def test_bundle_files_returns_sorted_unique_paths() -> None:
    paths = bundle_files()
    paths_str = [p.as_posix() for p in paths]
    assert paths_str == sorted(paths_str), "bundle_files() must be sorted for determinism"
    # No .gitkeep should leak through — it's the placeholder marker.
    assert not any(p.name == ".gitkeep" for p in paths)


def test_classify_install_recognizes_site_packages() -> None:
    classified = _classify_install(
        Path("/x/y/site-packages/asyncviz/dashboard/static"),
    )
    assert isinstance(classified, PackagedInstall)


def test_classify_install_recognizes_editable_via_pyproject(tmp_path: Path) -> None:
    # Construct a fake editable layout: <root>/asyncviz/dashboard/static
    # with a pyproject.toml at <root>.
    root = tmp_path / "checkout"
    bundle = root / "asyncviz" / "dashboard" / "static"
    bundle.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert isinstance(_classify_install(bundle), EditableInstall)


def test_classify_install_falls_back_to_unknown(tmp_path: Path) -> None:
    nowhere = tmp_path / "nowhere" / "static"
    assert isinstance(_classify_install(nowhere), UnknownInstall)


def test_required_missing_reports_missing_index(tmp_path: Path) -> None:
    bundle = tmp_path / "static"
    bundle.mkdir()
    assert _required_missing(bundle) == ("index.html",)
    (bundle / "index.html").write_text("<html></html>")
    assert _required_missing(bundle) == ()
