"""Atomic copy primitives used by the publisher.

Splits the file-IO from the orchestration so tests can drive the
copy step against a fake source dir + verify the destination layout
without going through ``subprocess`` or ``npm``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from asyncviz.dashboard.assets.asset_layout import IGNORED_FILES


def wipe_published_bundle(static_dir: Path, *, keep: set[str] | None = None) -> int:
    """Delete every file under ``static_dir`` except ``keep`` + ``.gitkeep``.

    Returns the number of removed entries. Empty directories are
    removed alongside their files so ``ls`` shows a clean slate.
    """
    if not static_dir.is_dir():
        return 0
    preserve = {".gitkeep"} | (keep or set())
    removed = 0
    for entry in static_dir.iterdir():
        if entry.name in preserve:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
        removed += 1
    return removed


def copy_bundle(source: Path, destination: Path) -> int:
    """Mirror ``source`` into ``destination``. Returns file count copied.

    Skips :data:`IGNORED_FILES` and never overwrites the destination's
    ``.gitkeep`` marker.
    """
    if not source.is_dir():
        raise FileNotFoundError(f"source bundle missing: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    source_resolved = source.resolve()
    for src_path in source.rglob("*"):
        if not src_path.is_file():
            continue
        if src_path.name in IGNORED_FILES:
            continue
        relative = src_path.resolve().relative_to(source_resolved)
        dest_path = destination / relative
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)
        copied += 1
    return copied
