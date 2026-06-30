from __future__ import annotations

from pathlib import Path

from asyncviz.dashboard.assets.asset_integrity import (
    atomic_write_text,
    content_type_for,
    sha256_file,
)
from asyncviz.dashboard.assets.asset_layout import (
    ASSETS_DIRECTORY,
    IGNORED_FILES,
    INDEX_HTML,
    asset_relative_path,
)


def test_index_html_constant_matches_disk_name() -> None:
    assert INDEX_HTML == "index.html"


def test_assets_directory_constant() -> None:
    assert ASSETS_DIRECTORY == "assets"


def test_ignored_files_includes_common_noise() -> None:
    assert ".DS_Store" in IGNORED_FILES
    assert ".gitkeep" in IGNORED_FILES


def test_asset_relative_path_uses_posix() -> None:
    assert asset_relative_path("assets", "main.js") == "assets/main.js"


def test_sha256_file_round_trips(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    p.write_bytes(b"hello world")
    assert len(sha256_file(p)) == 64


def test_content_type_handles_known_extensions(tmp_path: Path) -> None:
    assert (
        content_type_for(tmp_path / "a.js").startswith("application/javascript")
        or content_type_for(tmp_path / "a.js") == "text/javascript"
    )
    assert content_type_for(tmp_path / "a.css") == "text/css"
    assert content_type_for(tmp_path / "a.unknown") == "application/octet-stream"


def test_atomic_write_text_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    atomic_write_text(target, "{}")
    assert target.read_text() == "{}"
    # tmp file should be gone.
    assert not (target.with_suffix(".json.tmp")).exists()
