from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from asyncviz.packaging import (
    validate_sdist,
    validate_wheel,
)
from asyncviz.packaging.wheel_validation import _strip_sdist_prefix


def _make_wheel(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, mode="w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return path


def _make_sdist(path: Path, prefix: str, files: dict[str, bytes]) -> Path:
    with tarfile.open(path, mode="w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name=f"{prefix}/{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return path


REQUIRED_WHEEL_LAYOUT: dict[str, bytes] = {
    "asyncviz/__init__.py": b"",
    "asyncviz/__main__.py": b"",
    "asyncviz/py.typed": b"",
    "asyncviz/packaging/__init__.py": b"",
    "asyncviz/dashboard/__init__.py": b"",
    "asyncviz/dashboard/static/index.html": b"<html></html>",
    "asyncviz/dashboard/static/assets/main.js": b"console.log('hi');",
}


def test_validate_wheel_passes_on_complete_layout(tmp_path: Path) -> None:
    wheel = _make_wheel(tmp_path / "asyncviz-0.0.0-py3-none-any.whl", REQUIRED_WHEEL_LAYOUT)
    report = validate_wheel(wheel)
    assert report.ok, report.issues
    assert report.artifact_kind == "wheel"
    assert report.static_files >= 2


def test_validate_wheel_reports_missing_static(tmp_path: Path) -> None:
    static_prefix = "asyncviz/dashboard/static"
    layout = {
        k: v for k, v in REQUIRED_WHEEL_LAYOUT.items() if not k.startswith(static_prefix)
    }
    wheel = _make_wheel(tmp_path / "asyncviz-0.0.0-py3-none-any.whl", layout)
    report = validate_wheel(wheel)
    assert not report.ok
    codes = {issue.code for issue in report.issues}
    assert "missing-file" in codes or "missing-static" in codes


def test_validate_wheel_reports_missing_assets_dir(tmp_path: Path) -> None:
    assets_prefix = "asyncviz/dashboard/static/assets"
    layout = {
        k: v for k, v in REQUIRED_WHEEL_LAYOUT.items() if not k.startswith(assets_prefix)
    }
    wheel = _make_wheel(tmp_path / "asyncviz-0.0.0-py3-none-any.whl", layout)
    report = validate_wheel(wheel)
    assert not report.ok
    assert any(issue.code == "missing-prefix" for issue in report.issues)


def test_validate_wheel_handles_missing_artifact(tmp_path: Path) -> None:
    report = validate_wheel(tmp_path / "nope.whl")
    assert not report.ok
    assert any(issue.code == "missing" for issue in report.issues)


def test_validate_wheel_handles_corrupt_artifact(tmp_path: Path) -> None:
    bad = tmp_path / "bad.whl"
    bad.write_bytes(b"this is not a zip file")
    report = validate_wheel(bad)
    assert not report.ok
    assert any(issue.code == "corrupt" for issue in report.issues)


def test_validate_sdist_passes_on_complete_layout(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": b"[project]\nname='asyncviz'\n",
        "README.md": b"hi",
        "LICENSE": b"mit",
        "asyncviz/__init__.py": b"",
        "asyncviz/packaging/__init__.py": b"",
        "asyncviz/dashboard/static/index.html": b"<html></html>",
        "asyncviz/dashboard/static/assets/x.js": b"x",
    }
    sdist = _make_sdist(tmp_path / "asyncviz-0.0.0.tar.gz", "asyncviz-0.0.0", files)
    report = validate_sdist(sdist)
    assert report.ok, report.issues
    assert report.static_files >= 2


def test_validate_sdist_reports_missing_pyproject(tmp_path: Path) -> None:
    files = {
        "README.md": b"hi",
        "asyncviz/__init__.py": b"",
        "asyncviz/dashboard/static/index.html": b"<html></html>",
    }
    sdist = _make_sdist(tmp_path / "asyncviz-0.0.0.tar.gz", "asyncviz-0.0.0", files)
    report = validate_sdist(sdist)
    assert not report.ok


def test_validate_sdist_handles_missing_artifact(tmp_path: Path) -> None:
    report = validate_sdist(tmp_path / "missing.tar.gz")
    assert not report.ok
    assert any(issue.code == "missing" for issue in report.issues)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("asyncviz-0.0.0/foo.py", "foo.py"),
        ("asyncviz-0.0.0/asyncviz/__init__.py", "asyncviz/__init__.py"),
        ("noseparator", "noseparator"),
    ],
)
def test_strip_sdist_prefix(name: str, expected: str) -> None:
    assert _strip_sdist_prefix(name) == expected
