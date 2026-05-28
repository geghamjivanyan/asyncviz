"""Export helpers for finalized recordings.

For now: zip an entire session directory into a single ``.avzr`` (or
caller-supplied ``.zip``) bundle for portable transport. Future
extensions can add streaming compression, S3 upload, etc.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExportResult:
    bundle_path: Path
    bytes_written: int
    files_included: int


def export_session_to_zip(
    session_dir: Path, output_path: Path, *, compression: int = zipfile.ZIP_DEFLATED,
) -> ExportResult:
    """Bundle ``session_dir`` (recursively) into a zip archive at
    ``output_path``. Returns an :class:`ExportResult`.

    Safe to call on an in-progress session — files that change mid-write
    are skipped if they fail to open; the rest are bundled as-is. For
    crash-safe exports, stop the recorder first.
    """
    if not session_dir.exists() or not session_dir.is_dir():
        raise FileNotFoundError(f"session dir does not exist: {session_dir}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files_included = 0
    with zipfile.ZipFile(output_path, mode="w", compression=compression) as zf:
        for path in sorted(session_dir.rglob("*")):
            if not path.is_file():
                continue
            arcname = path.relative_to(session_dir).as_posix()
            try:
                zf.write(path, arcname=arcname)
            except OSError:
                continue
            files_included += 1
    return ExportResult(
        bundle_path=output_path,
        bytes_written=output_path.stat().st_size,
        files_included=files_included,
    )
