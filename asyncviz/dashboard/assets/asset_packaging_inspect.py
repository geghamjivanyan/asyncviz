"""Inspect a built wheel / sdist for the embedded frontend.

Used by ``scripts/packaging/inspect_wheel_assets.py`` to enumerate
the static files inside an artifact without unpacking it. Mirrors
the validator surface so the same diagnostics shape applies whether
the bundle is on disk or inside a zip.
"""

from __future__ import annotations

import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ArchiveKind = Literal["wheel", "sdist"]


@dataclass(frozen=True, slots=True)
class WheelAssetEntry:
    name: str
    size_bytes: int
    is_index: bool
    is_manifest: bool


@dataclass(frozen=True, slots=True)
class WheelAssetReport:
    artifact: Path
    kind: ArchiveKind
    static_entries: tuple[WheelAssetEntry, ...] = field(default_factory=tuple)
    total_files: int = 0
    static_count: int = 0
    has_index: bool = False
    has_manifest: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


def _strip_sdist_prefix(name: str) -> str:
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else parts[0]


def inspect_wheel(path: Path) -> WheelAssetReport:
    if not path.is_file():
        return WheelAssetReport(artifact=path, kind="wheel", notes=("file missing",))
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
    return _build_report(
        path,
        "wheel",
        [(info.filename, info.file_size) for info in infos if not info.is_dir()],
    )


def inspect_sdist(path: Path) -> WheelAssetReport:
    if not path.is_file():
        return WheelAssetReport(artifact=path, kind="sdist", notes=("file missing",))
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
    entries: list[tuple[str, int]] = []
    for member in members:
        if not member.isfile():
            continue
        entries.append((_strip_sdist_prefix(member.name), member.size))
    return _build_report(path, "sdist", entries)


def _build_report(
    path: Path,
    kind: ArchiveKind,
    entries: list[tuple[str, int]],
) -> WheelAssetReport:
    static_prefix = "asyncviz/dashboard/static/"
    static_entries: list[WheelAssetEntry] = []
    has_index = False
    has_manifest = False
    for name, size in entries:
        if not name.startswith(static_prefix):
            continue
        relative = name[len(static_prefix) :]
        if not relative:
            continue
        is_index = relative == "index.html"
        is_manifest = relative == "build.json"
        if is_index:
            has_index = True
        if is_manifest:
            has_manifest = True
        static_entries.append(
            WheelAssetEntry(
                name=relative,
                size_bytes=size,
                is_index=is_index,
                is_manifest=is_manifest,
            ),
        )
    static_entries.sort(key=lambda e: e.name)
    return WheelAssetReport(
        artifact=path,
        kind=kind,
        static_entries=tuple(static_entries),
        total_files=len(entries),
        static_count=len(static_entries),
        has_index=has_index,
        has_manifest=has_manifest,
    )
