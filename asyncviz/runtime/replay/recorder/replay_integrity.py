"""Artifact integrity helpers.

* :func:`open_marker` / :func:`finalize_marker` manage the
  ``INCOMPLETE`` tombstone so abrupt termination leaves a recognizable
  bundle state.
* :func:`sha256_file` returns a lowercase-hex SHA-256 — used in the
  manifest to detect chunk tampering / partial writes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from asyncviz.runtime.replay.artifacts.replay_layout import INCOMPLETE_MARKER

_BUFFER_SIZE = 64 * 1024


def open_marker(bundle_dir: Path) -> Path:
    """Create the ``INCOMPLETE`` tombstone."""
    marker = bundle_dir / INCOMPLETE_MARKER
    marker.write_text("recording in progress\n", encoding="utf-8")
    return marker


def finalize_marker(bundle_dir: Path) -> None:
    """Remove the ``INCOMPLETE`` tombstone. Idempotent."""
    marker = bundle_dir / INCOMPLETE_MARKER
    if marker.exists():
        marker.unlink()


def sha256_file(path: Path) -> str:
    """Return the lowercase-hex SHA-256 of ``path``'s bytes."""
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_BUFFER_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_write_text(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path`` atomically via ``rename``.

    On POSIX + Windows ``Path.rename`` is atomic on the same
    filesystem; we lean on that to keep the manifest / metadata
    files free from torn writes during a crash.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
