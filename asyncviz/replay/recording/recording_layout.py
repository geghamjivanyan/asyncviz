"""On-disk file layout for a recording session.

A recording session is a directory containing:

    <session_dir>/
    ├── manifest.json              ← session metadata + file inventory
    ├── events/
    │   ├── 000001.ndjson          ← rotating event chunks
    │   ├── 000002.ndjson
    │   └── ...
    ├── snapshots/
    │   ├── 000001.json            ← runtime snapshot at chunk boundary
    │   └── ...
    └── index.json                 ← sequence → (chunk, offset) (optional)

Every file is plain JSON / NDJSON so a recording is portable across
platforms + tools — `cat events/*.ndjson` is a valid pipeline.
Filename digits are zero-padded to 6 places to keep lexicographic
sort order matching numeric chunk order, which simplifies the read
side dramatically.
"""

from __future__ import annotations

from pathlib import Path

MANIFEST_FILENAME = "manifest.json"
INDEX_FILENAME = "index.json"
EVENTS_DIRNAME = "events"
SNAPSHOTS_DIRNAME = "snapshots"

CHUNK_DIGITS = 6
CHUNK_EXTENSION = "ndjson"
SNAPSHOT_EXTENSION = "json"

#: Bumped when the on-disk layout changes in a non-backwards-compatible
#: way. Recordings whose manifest version differs from this either need
#: a migration step or are simply not loadable by this version.
SCHEMA_VERSION: int = 1


def chunk_filename(index: int, *, extension: str = CHUNK_EXTENSION) -> str:
    """``index=1, extension="ndjson"`` → ``"000001.ndjson"``."""
    if index < 1:
        raise ValueError(f"chunk index must be >= 1 (got {index})")
    return f"{index:0{CHUNK_DIGITS}d}.{extension}"


def events_chunk_path(session_dir: Path, index: int) -> Path:
    return session_dir / EVENTS_DIRNAME / chunk_filename(index)


def snapshot_chunk_path(session_dir: Path, index: int) -> Path:
    return (
        session_dir
        / SNAPSHOTS_DIRNAME
        / chunk_filename(
            index,
            extension=SNAPSHOT_EXTENSION,
        )
    )


def manifest_path(session_dir: Path) -> Path:
    return session_dir / MANIFEST_FILENAME


def index_path(session_dir: Path) -> Path:
    return session_dir / INDEX_FILENAME


def events_dir(session_dir: Path) -> Path:
    return session_dir / EVENTS_DIRNAME


def snapshots_dir(session_dir: Path) -> Path:
    return session_dir / SNAPSHOTS_DIRNAME
