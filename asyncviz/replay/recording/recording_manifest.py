"""Manifest read/write helpers.

The manifest is written atomically via a temp-file + rename so a
crash mid-write never leaves a half-written manifest on disk.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from asyncviz.replay.recording.recording_layout import manifest_path
from asyncviz.replay.recording.recording_metadata import RecordingMetadata
from asyncviz.replay.recording.recording_paths import atomic_replace
from asyncviz.replay.recording.recording_tracing import record_recording_trace


def write_manifest(session_dir: Path, metadata: RecordingMetadata) -> Path:
    """Atomically persist ``metadata`` as the session's manifest.

    Returns the final manifest path. Crash-safe — the temp file is
    written + ``os.replace``-d into the target, so readers either see
    the previous manifest or the new one, never a torn write.
    """
    target = manifest_path(session_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(metadata.to_dict(), indent=2, sort_keys=True) + "\n"
    # NamedTemporaryFile + atomic rename — same trick the queue/replay
    # bundle exporter uses elsewhere in the codebase.
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=".manifest.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
        atomic_replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    record_recording_trace("manifest-written", str(target))
    return target


def read_manifest(session_dir: Path) -> RecordingMetadata | None:
    """Load the manifest, or return ``None`` when missing.

    Raises :class:`ValueError` for a malformed JSON manifest — callers
    can either ignore (treat as missing) or run the recovery layer.
    """
    target = manifest_path(session_dir)
    if not target.exists():
        return None
    raw = target.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest at {target} is malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"manifest at {target} must be a JSON object")
    return RecordingMetadata.from_dict(data)
