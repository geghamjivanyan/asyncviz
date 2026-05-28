"""Integrity primitives for the published frontend bundle.

* :func:`sha256_file` — streaming hash for one file.
* :func:`content_type_for` — MIME-type guess from extension.
* :func:`atomic_write_text` — write-then-rename so a crash never
  leaves the manifest file half-written.
"""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

_BUFFER_SIZE = 64 * 1024


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


def content_type_for(path: Path) -> str:
    """Best-effort MIME-type guess. Falls back to
    ``application/octet-stream``."""
    guessed, _ = mimetypes.guess_type(path.as_posix())
    return guessed or "application/octet-stream"


def atomic_write_text(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path`` via tmp + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
