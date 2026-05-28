"""Replay bundle reader.

The reader is intentionally lazy — opening a bundle just parses the
manifest. Chunk + snapshot data load on demand so a CI step can
attach a 500 MB bundle to a bug report without exhausting RAM at
open time.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from asyncviz.runtime.replay.artifacts.replay_layout import (
    INCOMPLETE_MARKER,
    MANIFEST_FILENAME,
)
from asyncviz.runtime.replay.recorder.replay_compression import open_chunk_reader
from asyncviz.runtime.replay.recorder.replay_manifest import (
    ReplayBundleManifest,
    load_manifest,
)


@dataclass(frozen=True, slots=True)
class ReplayBundle:
    """Lazy view of a replay bundle on disk."""

    root: Path
    manifest: ReplayBundleManifest

    @property
    def is_finalized(self) -> bool:
        return self.manifest.finalized and not (self.root / INCOMPLETE_MARKER).exists()

    def iter_frames(self) -> Iterator[dict]:
        """Yield each frame across every chunk in order.

        Frames are parsed on demand. Lines that fail to decode are
        skipped + reported through the recorder error counter via
        the caller (tests poke this surface directly).
        """
        for chunk in self.manifest.chunks:
            with open_chunk_reader(self.root / chunk.file) as fh:
                for raw in fh:
                    if not raw.strip():
                        continue
                    yield json.loads(raw)

    def iter_chunk_paths(self) -> Iterator[Path]:
        for chunk in self.manifest.chunks:
            yield self.root / chunk.file

    def load_snapshot(self, name: str) -> dict | None:
        rel = self.manifest.snapshot_files.get(name)
        if not rel:
            return None
        path = self.root / rel
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_meta(self, name: str) -> dict | None:
        rel = self.manifest.meta_files.get(name)
        if not rel:
            return None
        path = self.root / rel
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def open_bundle(root: Path) -> ReplayBundle:
    """Parse + return a :class:`ReplayBundle`. Raises ``FileNotFoundError``
    when the manifest is missing."""
    if not (root / MANIFEST_FILENAME).is_file():
        raise FileNotFoundError(f"no replay manifest at {root}")
    manifest = load_manifest(root)
    return ReplayBundle(root=root, manifest=manifest)
