"""Read / write the canonical bundle manifest.

The manifest is the entry point for every replay-side tool. It carries
the schema version + chunk inventory + integrity hashes — enough that
a reader can refuse to open a corrupted bundle without parsing
chunks.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from asyncviz.runtime.replay.artifacts.replay_layout import (
    ARTIFACT_SCHEMA_VERSION,
    MANIFEST_FILENAME,
)
from asyncviz.runtime.replay.recorder.replay_integrity import atomic_write_text


@dataclass(frozen=True, slots=True)
class ChunkManifestEntry:
    """One chunk record in the manifest."""

    file: str
    sequence_start: int
    sequence_end: int
    event_count: int
    compressed_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ReplayBundleManifest:
    """Top-level manifest schema."""

    schema_version: int
    asyncviz_version: str
    runtime_id: str
    bundle_id: str
    created_at_iso: str
    finalized: bool
    event_count: int
    first_sequence: int | None
    last_sequence: int | None
    chunks: tuple[ChunkManifestEntry, ...]
    snapshot_files: dict[str, str]
    meta_files: dict[str, str]
    notes: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


def build_manifest(
    *,
    asyncviz_version: str,
    runtime_id: str,
    bundle_id: str,
    created_at_iso: str,
    finalized: bool,
    chunks: tuple[ChunkManifestEntry, ...],
    snapshot_files: dict[str, str],
    meta_files: dict[str, str],
    extras: dict[str, Any] | None = None,
    notes: str = "",
) -> ReplayBundleManifest:
    event_count = sum(c.event_count for c in chunks)
    first_sequence: int | None = None
    last_sequence: int | None = None
    if chunks:
        first_sequence = min(c.sequence_start for c in chunks)
        last_sequence = max(c.sequence_end for c in chunks)
    return ReplayBundleManifest(
        schema_version=ARTIFACT_SCHEMA_VERSION,
        asyncviz_version=asyncviz_version,
        runtime_id=runtime_id,
        bundle_id=bundle_id,
        created_at_iso=created_at_iso,
        finalized=finalized,
        event_count=event_count,
        first_sequence=first_sequence,
        last_sequence=last_sequence,
        chunks=chunks,
        snapshot_files=dict(snapshot_files),
        meta_files=dict(meta_files),
        notes=notes,
        extras=dict(extras or {}),
    )


def write_manifest(bundle_dir: Path, manifest: ReplayBundleManifest) -> Path:
    """Persist ``manifest`` to ``bundle_dir/manifest.json`` atomically."""
    path = bundle_dir / MANIFEST_FILENAME
    payload = {
        "schema_version": manifest.schema_version,
        "asyncviz_version": manifest.asyncviz_version,
        "runtime_id": manifest.runtime_id,
        "bundle_id": manifest.bundle_id,
        "created_at_iso": manifest.created_at_iso,
        "finalized": manifest.finalized,
        "event_count": manifest.event_count,
        "first_sequence": manifest.first_sequence,
        "last_sequence": manifest.last_sequence,
        "chunks": [asdict(chunk) for chunk in manifest.chunks],
        "snapshot_files": dict(manifest.snapshot_files),
        "meta_files": dict(manifest.meta_files),
        "notes": manifest.notes,
        "extras": dict(manifest.extras),
    }
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def load_manifest(bundle_dir: Path) -> ReplayBundleManifest:
    path = bundle_dir / MANIFEST_FILENAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = tuple(
        ChunkManifestEntry(
            file=entry["file"],
            sequence_start=int(entry["sequence_start"]),
            sequence_end=int(entry["sequence_end"]),
            event_count=int(entry["event_count"]),
            compressed_bytes=int(entry["compressed_bytes"]),
            sha256=str(entry["sha256"]),
        )
        for entry in payload.get("chunks", [])
    )
    return ReplayBundleManifest(
        schema_version=int(payload.get("schema_version", ARTIFACT_SCHEMA_VERSION)),
        asyncviz_version=str(payload.get("asyncviz_version", "")),
        runtime_id=str(payload.get("runtime_id", "")),
        bundle_id=str(payload.get("bundle_id", "")),
        created_at_iso=str(payload.get("created_at_iso", "")),
        finalized=bool(payload.get("finalized", False)),
        event_count=int(payload.get("event_count", 0)),
        first_sequence=payload.get("first_sequence"),
        last_sequence=payload.get("last_sequence"),
        chunks=chunks,
        snapshot_files=dict(payload.get("snapshot_files", {})),
        meta_files=dict(payload.get("meta_files", {})),
        notes=str(payload.get("notes", "")),
        extras=dict(payload.get("extras", {})),
    )
