"""On-disk writer for replay chunks.

Owns:

* The current open chunk (compressed or raw).
* The chunk-roll policy.
* Atomic chunk finalize (close → fsync → rename).
* Manifest assembly from per-chunk metadata.

The writer is intentionally thread-affine — only the worker thread
inside :class:`ReplayRecorder` calls it. Tests can drive it directly
on the main thread for unit testing.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from asyncviz.runtime.replay.artifacts.replay_layout import (
    CHUNK_DIRECTORY,
    build_chunk_name,
)
from asyncviz.runtime.replay.recorder.replay_chunking import ChunkPolicy
from asyncviz.runtime.replay.recorder.replay_compression import (
    CompressionMode,
    open_chunk_writer,
)
from asyncviz.runtime.replay.recorder.replay_integrity import sha256_file
from asyncviz.runtime.replay.recorder.replay_manifest import (
    ChunkManifestEntry,
)
from asyncviz.runtime.replay.recorder.replay_tracing import record_recorder_trace


@dataclass(slots=True)
class _OpenChunk:
    """Mutable per-chunk state held by the writer."""

    index: int
    path: Path
    fh: BinaryIO
    first_sequence: int | None = None
    last_sequence: int | None = None
    event_count: int = 0
    serialized_bytes: int = 0


@dataclass(slots=True)
class ReplayWriter:
    """Append-only chunked NDJSON writer for replay frames."""

    bundle_dir: Path
    compression: CompressionMode
    chunk_policy: ChunkPolicy
    _open_chunk: _OpenChunk | None = field(default=None, init=False)
    _finalized_chunks: list[ChunkManifestEntry] = field(default_factory=list, init=False)
    _closed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        (self.bundle_dir / CHUNK_DIRECTORY).mkdir(parents=True, exist_ok=True)

    @property
    def finalized_chunks(self) -> tuple[ChunkManifestEntry, ...]:
        return tuple(self._finalized_chunks)

    def write_record(self, *, sequence: int, payload: bytes) -> None:
        """Append one NDJSON-encoded ``payload`` (bytes ending in ``\\n``)."""
        if self._closed:
            raise RuntimeError("writer is closed")
        chunk = self._open_chunk
        if chunk is None:
            chunk = self._open_new_chunk()
        if chunk.first_sequence is None:
            chunk.first_sequence = sequence
        chunk.last_sequence = sequence
        chunk.event_count += 1
        chunk.serialized_bytes += len(payload)
        chunk.fh.write(payload)
        self.chunk_policy.record(len(payload))
        if self.chunk_policy.should_roll():
            self._roll_chunk()

    def flush(self) -> None:
        """Flush the current chunk's IO buffer to disk."""
        if self._open_chunk is not None:
            self._flush_handle(self._open_chunk.fh)

    def close(self) -> None:
        """Finalize the current chunk + mark the writer closed."""
        if self._closed:
            return
        if self._open_chunk is not None:
            self._roll_chunk(force=True)
        self._closed = True

    # ── internals ─────────────────────────────────────────────────────

    def _open_new_chunk(self) -> _OpenChunk:
        index = self.chunk_policy.chunks_rolled + len(self._finalized_chunks)
        # On a freshly-opened writer ``chunks_rolled`` is 0; on a roll
        # we increment via ``reset_for_new_chunk`` so the new chunk
        # index matches the previously rolled count.
        path = self.bundle_dir / CHUNK_DIRECTORY / build_chunk_name(
            index, compressed=self.compression is CompressionMode.GZIP,
        )
        fh = open_chunk_writer(path, self.compression)
        self._open_chunk = _OpenChunk(index=index, path=path, fh=fh)
        record_recorder_trace("chunk-rolled", f"index={index} path={path.name}")
        return self._open_chunk

    def _roll_chunk(self, *, force: bool = False) -> None:
        chunk = self._open_chunk
        if chunk is None:
            return
        if chunk.event_count == 0 and not force:
            return
        self._flush_handle(chunk.fh)
        chunk.fh.close()
        if chunk.event_count == 0:
            # Empty chunk on a forced close — drop the file so the
            # bundle never advertises an empty chunk.
            import contextlib

            with contextlib.suppress(FileNotFoundError):
                chunk.path.unlink()
            self._open_chunk = None
            return
        digest = sha256_file(chunk.path)
        size = chunk.path.stat().st_size
        entry = ChunkManifestEntry(
            file=f"{CHUNK_DIRECTORY}/{chunk.path.name}",
            sequence_start=chunk.first_sequence or 0,
            sequence_end=chunk.last_sequence or 0,
            event_count=chunk.event_count,
            compressed_bytes=size,
            sha256=digest,
        )
        self._finalized_chunks.append(entry)
        record_recorder_trace(
            "chunk-finalized",
            f"index={chunk.index} events={chunk.event_count} bytes={size}",
        )
        self._open_chunk = None
        self.chunk_policy.reset_for_new_chunk()

    @staticmethod
    def _flush_handle(fh: BinaryIO) -> None:
        try:
            fh.flush()
        except (OSError, ValueError):
            return
        # ``gzip.GzipFile`` doesn't expose ``fileno`` directly; only
        # call ``fsync`` when the handle wraps a real file descriptor.
        fileno = getattr(fh, "fileno", None)
        if callable(fileno):
            try:
                import os

                os.fsync(fileno())
            except (OSError, io.UnsupportedOperation):
                return
