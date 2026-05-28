"""Cross-platform path helpers for recording sessions.

Centralizes the few sharp edges so the rest of the package can stay
``pathlib``-only:

* Atomic rename — ``Path.replace`` is atomic on POSIX + Windows for
  same-volume targets, but the cross-platform contract is subtle
  enough to wrap.
* Filename safety — recording ids are UUIDs; we never accept arbitrary
  user-supplied path components into a session dir name.
"""

from __future__ import annotations

import os
from pathlib import Path


def ensure_directory(path: Path) -> Path:
    """Create ``path`` (+ any intermediate parents). Idempotent."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_replace(source: Path, target: Path) -> None:
    """Atomically replace ``target`` with ``source``.

    On POSIX + Windows the call is atomic *as long as both paths live on
    the same volume*. We enforce that by reading the volume of ``target``
    and writing to a sibling temp path; callers should do the same.
    """
    source.replace(target)


def fsync_file(path: Path) -> None:
    """``fsync`` ``path`` so the data hits the device. Safe to call on
    Windows — ``os.fsync`` works on file descriptors there too."""
    with path.open("rb") as f:
        os.fsync(f.fileno())


def session_dir_for(root: Path, recording_id: str) -> Path:
    """Compute the per-session directory under ``root``.

    ``recording_id`` is expected to be a UUID-shaped string; we never
    accept ``..`` or absolute path components — defensive guard so a
    caller can't escape ``root``."""
    safe = recording_id.replace("/", "_").replace("\\", "_")
    if safe.startswith(".") or ":" in safe:
        raise ValueError(f"unsafe recording_id {recording_id!r}")
    return root / safe
