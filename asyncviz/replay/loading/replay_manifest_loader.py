"""Manifest resolution for the replay loader.

The recording layer owns :func:`read_manifest`. The loader-side
wrapper adds the path-resolution + sanity-check work the loader
itself wants: confirm every manifest-declared chunk exists on disk,
confirm snapshots exist, surface any drift as a structured
:class:`ManifestLoadResult` so callers can decide whether to proceed.

Missing chunks are non-fatal by default — recording sessions
sometimes ship with snapshots stripped, or with the manifest
pre-finalized while a tail chunk is still being written. The loader
prefers to report what's missing rather than crash on construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from asyncviz.replay.loading.models.replay_session import ReplaySession
from asyncviz.replay.recording.recording_layout import (
    EVENTS_DIRNAME,
    events_chunk_path,
    snapshot_chunk_path,
)
from asyncviz.replay.recording.recording_manifest import read_manifest
from asyncviz.replay.recording.recording_metadata import RecordingMetadata


class ManifestLoadError(ValueError):
    """Raised when a session directory cannot be resolved to a
    well-formed :class:`RecordingMetadata`."""


@dataclass(frozen=True, slots=True)
class ManifestLoadResult:
    """Outcome of resolving a session's manifest + on-disk layout."""

    session: ReplaySession
    missing_chunk_paths: tuple[Path, ...]
    missing_snapshot_paths: tuple[Path, ...]

    @property
    def fully_resolved(self) -> bool:
        return not self.missing_chunk_paths and not self.missing_snapshot_paths


def load_manifest(session_dir: Path) -> ManifestLoadResult:
    """Read the manifest + resolve every chunk/snapshot path.

    Raises :class:`ManifestLoadError` only when the manifest itself
    is unreadable or unparseable. Missing chunk/snapshot files are
    reported via the result, not raised — the loader can still
    operate against a partial recording.
    """
    metadata = read_manifest(session_dir)
    if metadata is None:
        raise ManifestLoadError(f"no manifest.json at {session_dir}")
    return _resolve_layout(session_dir=session_dir, metadata=metadata)


def load_manifest_or_rebuild(session_dir: Path) -> ManifestLoadResult:
    """Like :func:`load_manifest` but reconstructs a minimal
    metadata stub if the manifest is missing.

    Useful when a recording's writer crashed before the first
    manifest flush: the chunks are still on disk + can be replayed,
    we just need to scan the events directory to find them.
    """
    try:
        return load_manifest(session_dir)
    except ManifestLoadError:
        events_directory = session_dir / EVENTS_DIRNAME
        chunk_files = (
            sorted(events_directory.glob("*.ndjson"))
            if events_directory.exists()
            else []
        )
        metadata = RecordingMetadata(
            schema_version=1,
            recording_id=session_dir.name,
            runtime_id="",
            asyncviz_version="",
            started_at_ns=0,
            stopped_at_ns=0,
            chunks=(),
            snapshots=(),
            event_count=0,
            chunk_count=len(chunk_files),
            snapshot_count=0,
            last_sequence=0,
            finalized=False,
        )
        return ManifestLoadResult(
            session=ReplaySession(
                session_dir=session_dir,
                metadata=metadata,
                chunk_paths=tuple(chunk_files),
                snapshot_paths=(),
                detected_format="auto",
            ),
            missing_chunk_paths=(),
            missing_snapshot_paths=(),
        )


def _resolve_layout(
    *, session_dir: Path, metadata: RecordingMetadata,
) -> ManifestLoadResult:
    chunk_paths: list[Path] = []
    missing_chunks: list[Path] = []
    for chunk in metadata.chunks:
        path = events_chunk_path(session_dir, chunk.index)
        chunk_paths.append(path)
        if not path.exists():
            missing_chunks.append(path)

    snapshot_paths: list[Path] = []
    missing_snapshots: list[Path] = []
    for snapshot in metadata.snapshots:
        path = snapshot_chunk_path(session_dir, snapshot.index)
        snapshot_paths.append(path)
        if not path.exists():
            missing_snapshots.append(path)

    session = ReplaySession(
        session_dir=session_dir,
        metadata=metadata,
        chunk_paths=tuple(chunk_paths),
        snapshot_paths=tuple(snapshot_paths),
        detected_format="auto",
    )
    return ManifestLoadResult(
        session=session,
        missing_chunk_paths=tuple(missing_chunks),
        missing_snapshot_paths=tuple(missing_snapshots),
    )
