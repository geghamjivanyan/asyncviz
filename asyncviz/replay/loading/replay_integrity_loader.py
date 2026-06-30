"""Chunk-integrity verification at load time.

The recording layer hashes each chunk's bytes on close and stashes
the SHA-256 in the manifest's :class:`ChunkRecord`. The loader-side
verifier compares each chunk's on-disk hash to that recorded value
and reports any mismatch — either advisory (default) or fatal
(``strict``).

We deliberately recompute hashes here rather than trusting any
intermediate index, because integrity is the *whole point* of this
step and short-circuiting it would defeat the purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from asyncviz.replay.loading.replay_observability import get_loader_metrics
from asyncviz.replay.loading.replay_tracing import record_replay_trace
from asyncviz.replay.recording.recording_integrity import (
    compute_chunk_hash,
    verify_chunk_hash,
)
from asyncviz.replay.recording.recording_metadata import ChunkRecord


@dataclass(frozen=True, slots=True)
class ChunkIntegrityVerdict:
    """One chunk's integrity outcome."""

    chunk_index: int
    expected_sha256: str | None
    actual_sha256: str | None
    verified: bool
    skipped: bool = False
    reason: str = ""


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    """Whole-session integrity result."""

    verdicts: tuple[ChunkIntegrityVerdict, ...]

    @property
    def failed(self) -> tuple[ChunkIntegrityVerdict, ...]:
        return tuple(v for v in self.verdicts if not v.verified and not v.skipped)

    @property
    def all_verified(self) -> bool:
        return not self.failed


def verify_chunk(chunk: ChunkRecord, path: Path) -> ChunkIntegrityVerdict:
    """Verify one chunk against the SHA-256 in its record."""
    if not path.exists():
        return ChunkIntegrityVerdict(
            chunk_index=chunk.index,
            expected_sha256=chunk.sha256,
            actual_sha256=None,
            verified=False,
            skipped=True,
            reason="chunk file missing",
        )
    if not chunk.sha256:
        # Older recordings or in-flight rotation: nothing to compare.
        return ChunkIntegrityVerdict(
            chunk_index=chunk.index,
            expected_sha256=None,
            actual_sha256=compute_chunk_hash(path),
            verified=True,
            skipped=True,
            reason="manifest has no sha256 for this chunk",
        )
    actual = compute_chunk_hash(path)
    ok = verify_chunk_hash(path, chunk.sha256)
    if not ok:
        get_loader_metrics().record_integrity_failure()
        record_replay_trace(
            "integrity-failed",
            f"index={chunk.index} expected={chunk.sha256[:12]} actual={actual[:12]}",
        )
    return ChunkIntegrityVerdict(
        chunk_index=chunk.index,
        expected_sha256=chunk.sha256,
        actual_sha256=actual,
        verified=ok,
        skipped=False,
        reason="" if ok else "sha256 mismatch",
    )


def verify_session(
    chunks: tuple[ChunkRecord, ...],
    paths: tuple[Path, ...],
) -> IntegrityReport:
    """Verify every chunk in a session in order."""
    if len(chunks) != len(paths):
        raise ValueError(
            f"chunks ({len(chunks)}) and paths ({len(paths)}) must match",
        )
    verdicts = tuple(verify_chunk(c, p) for c, p in zip(chunks, paths, strict=True))
    return IntegrityReport(verdicts=verdicts)
