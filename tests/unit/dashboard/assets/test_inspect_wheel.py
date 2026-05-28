from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

from asyncviz.dashboard.assets import inspect_sdist, inspect_wheel


def _build_wheel(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return path


def _build_sdist(path: Path, prefix: str, files: dict[str, bytes]) -> Path:
    with tarfile.open(path, mode="w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name=f"{prefix}/{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return path


def test_inspect_wheel_lists_static_entries(tmp_path: Path) -> None:
    layout = {
        "asyncviz/__init__.py": b"",
        "asyncviz/dashboard/static/index.html": b"<html></html>",
        "asyncviz/dashboard/static/assets/main.js": b"x",
        "asyncviz/dashboard/static/build.json": b"{}",
    }
    wheel = _build_wheel(tmp_path / "x-0.0.0-py3-none-any.whl", layout)
    report = inspect_wheel(wheel)
    assert report.kind == "wheel"
    assert report.static_count == 3
    assert report.has_index is True
    assert report.has_manifest is True
    names = [entry.name for entry in report.static_entries]
    assert "index.html" in names
    assert "assets/main.js" in names


def test_inspect_wheel_handles_missing_static(tmp_path: Path) -> None:
    layout = {"asyncviz/__init__.py": b""}
    wheel = _build_wheel(tmp_path / "x.whl", layout)
    report = inspect_wheel(wheel)
    assert report.static_count == 0
    assert report.has_index is False


def test_inspect_sdist_strips_version_prefix(tmp_path: Path) -> None:
    files = {
        "asyncviz/dashboard/static/index.html": b"<html></html>",
        "asyncviz/dashboard/static/build.json": b"{}",
    }
    sdist = _build_sdist(tmp_path / "x-0.0.0.tar.gz", "x-0.0.0", files)
    report = inspect_sdist(sdist)
    assert report.kind == "sdist"
    assert report.has_index is True
    assert report.has_manifest is True
    names = [entry.name for entry in report.static_entries]
    assert "index.html" in names


def test_inspect_wheel_handles_missing_file(tmp_path: Path) -> None:
    report = inspect_wheel(tmp_path / "missing.whl")
    assert report.static_count == 0
    assert "file missing" in report.notes[0]
