"""Compression policy for chunk files.

Only two modes today (``none`` + ``gzip``). Keeping the enum + the
factory function in their own module lets a future zstd / lz4 path
land without touching the writer.
"""

from __future__ import annotations

import gzip
import io
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO


class CompressionMode(StrEnum):
    """Per-chunk compression mode."""

    NONE = "none"
    GZIP = "gzip"

    @property
    def file_extension(self) -> str:
        return ".gz" if self is CompressionMode.GZIP else ""


def open_chunk_writer(path: Path, mode: CompressionMode) -> BinaryIO:
    """Open ``path`` for writing using the chosen compression.

    Returns a binary file-like object; the writer always writes
    NDJSON-encoded UTF-8 bytes.
    """
    if mode is CompressionMode.GZIP:
        # mtime=0 → reproducible builds (same input → same bytes).
        return gzip.GzipFile(filename=str(path), mode="wb", mtime=0)
    return io.FileIO(str(path), mode="wb")


def open_chunk_reader(path: Path) -> BinaryIO:
    """Open ``path`` for reading; auto-detects gzip from the suffix."""
    if path.suffix == ".gz":
        return gzip.GzipFile(filename=str(path), mode="rb")
    return io.FileIO(str(path), mode="rb")
