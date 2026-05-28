"""Canonical replay event loader.

The :class:`ReplayEventLoader` is the top-level façade for
read-side replay infrastructure. Open a session, iterate frames,
seek by sequence or timestamp, reconstruct state at a point.

Lifecycle:

    loader = ReplayEventLoader.open(session_dir)
    try:
        for frame in loader.iter_frames():
            ...
    finally:
        loader.close()

Or use it as a context manager:

    with ReplayEventLoader.open(session_dir) as loader:
        ...

The loader is *lazy*: opening it only reads the manifest + resolves
paths. Decoding happens during iteration. Seeking walks the minimum
number of chunks needed to land on a sequence — it doesn't pre-load
anything beyond the index + snapshot lookup tables.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import Any

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading.models.frame_adapter import (
    FrameAdapter,
    select_frame_adapter,
)
from asyncviz.replay.loading.models.replay_session import (
    ReplaySession,
    ReplaySessionSummary,
)
from asyncviz.replay.loading.replay_chunk_loader import ReplayChunkLoader
from asyncviz.replay.loading.replay_configuration import ReplayLoaderConfig
from asyncviz.replay.loading.replay_cursor import ReplayCursor
from asyncviz.replay.loading.replay_filtering import FrameFilter
from asyncviz.replay.loading.replay_index import ReplayIndex
from asyncviz.replay.loading.replay_integrity_loader import (
    IntegrityReport,
    verify_session,
)
from asyncviz.replay.loading.replay_manifest_loader import (
    ManifestLoadResult,
    load_manifest,
    load_manifest_or_rebuild,
)
from asyncviz.replay.loading.replay_observability import get_loader_metrics
from asyncviz.replay.loading.replay_recovery_loader import (
    ChunkHealth,
    inspect_chunk,
)
from asyncviz.replay.loading.replay_seek import (
    SeekResult,
    seek_to_sequence,
    seek_to_timestamp,
)
from asyncviz.replay.loading.replay_snapshot_index import (
    ReplaySnapshotIndex,
    SnapshotEntry,
    load_snapshot_payload,
)
from asyncviz.replay.loading.replay_state_loader import (
    Reducer,
    StateReconstructionResult,
    default_collecting_reducer,
    reconstruct_state,
)
from asyncviz.replay.loading.replay_stream import ReplayStream
from asyncviz.replay.loading.replay_tracing import record_replay_trace
from asyncviz.replay.loading.replay_windowing import ReplayWindow
from asyncviz.replay.loading.utils.frame_navigation import (
    detect_format_from_session,
)


class ReplayEventLoader:
    """Top-level read-side façade for a recording session."""

    __slots__ = (
        "_adapter",
        "_closed",
        "_config",
        "_cursor",
        "_integrity",
        "_load_result",
        "_sequence_index",
        "_session",
        "_snapshot_index",
    )

    def __init__(
        self,
        config: ReplayLoaderConfig,
        load_result: ManifestLoadResult,
    ) -> None:
        self._config = config
        self._load_result = load_result
        self._session = load_result.session
        self._sequence_index = ReplayIndex.from_session_dir(
            config.session_dir, self._session.metadata,
        )
        self._snapshot_index = ReplaySnapshotIndex.from_records(
            self._session.snapshots, self._session.snapshot_paths,
        )
        self._adapter: FrameAdapter = self._resolve_adapter()
        self._cursor = ReplayCursor.at_start()
        self._integrity: IntegrityReport | None = None
        self._closed = False
        get_loader_metrics().record_session_opened()
        record_replay_trace("session-opened", str(config.session_dir))

    # ── construction ──────────────────────────────────────────────

    @staticmethod
    def open(
        session_dir: Path,
        *,
        config: ReplayLoaderConfig | None = None,
        rebuild_manifest_if_missing: bool = False,
    ) -> ReplayEventLoader:
        """Open a session for read."""
        cfg = config or ReplayLoaderConfig(session_dir=session_dir)
        result = (
            load_manifest_or_rebuild(cfg.session_dir)
            if rebuild_manifest_if_missing
            else load_manifest(cfg.session_dir)
        )
        loader = ReplayEventLoader(cfg, result)
        if cfg.verify_integrity:
            loader._integrity = verify_session(
                loader._session.chunks, loader._session.chunk_paths,
            )
        return loader

    # ── context manager ───────────────────────────────────────────

    def __enter__(self) -> ReplayEventLoader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Release per-loader bookkeeping. The loader holds no file
        handles between iterations, so close is mostly bookkeeping."""
        if self._closed:
            return
        self._closed = True
        get_loader_metrics().record_session_closed()
        record_replay_trace("session-closed", str(self._config.session_dir))

    # ── accessors ─────────────────────────────────────────────────

    @property
    def config(self) -> ReplayLoaderConfig:
        return self._config

    @property
    def session(self) -> ReplaySession:
        return self._session

    @property
    def cursor(self) -> ReplayCursor:
        return self._cursor

    @property
    def sequence_index(self) -> ReplayIndex:
        return self._sequence_index

    @property
    def snapshot_index(self) -> ReplaySnapshotIndex:
        return self._snapshot_index

    @property
    def adapter(self) -> FrameAdapter:
        return self._adapter

    @property
    def integrity(self) -> IntegrityReport | None:
        return self._integrity

    def summary(self) -> ReplaySessionSummary:
        metadata = self._session.metadata
        return ReplaySessionSummary(
            recording_id=metadata.recording_id,
            runtime_id=metadata.runtime_id,
            event_count=metadata.event_count,
            chunk_count=metadata.chunk_count,
            snapshot_count=metadata.snapshot_count,
            last_sequence=metadata.last_sequence,
            finalized=metadata.finalized,
            detected_format=self._adapter.format_name,
            chunk_paths_missing=tuple(str(p) for p in self._load_result.missing_chunk_paths),
            snapshot_paths_missing=tuple(
                str(p) for p in self._load_result.missing_snapshot_paths
            ),
        )

    # ── iteration ─────────────────────────────────────────────────

    def iter_frames(
        self,
        *,
        window: ReplayWindow | None = None,
        frame_filter: FrameFilter | None = None,
        from_cursor: ReplayCursor | None = None,
    ) -> Iterator[ReplayFrame]:
        """Yield frames across the whole recording. Optional
        ``window`` + ``frame_filter`` are applied lazily; iteration
        stops as soon as a frame falls *above* the window.

        When ``from_cursor`` is supplied, iteration starts strictly
        after ``cursor.last_sequence`` — the cursor's window bound is
        merged with the caller's window, so passing both works."""
        self._ensure_open()
        cursor_start = (
            from_cursor.last_sequence + 1 if from_cursor is not None else 0
        )
        merged_window = _merge_cursor_window(window, cursor_start)
        chunks = self._build_chunk_loaders()
        stream = ReplayStream(
            chunks,
            window=merged_window,
            frame_filter=frame_filter,
            initial_cursor=from_cursor or self._cursor,
        )
        for frame in stream:
            self._cursor = stream.cursor
            yield frame

    # ── seeking ───────────────────────────────────────────────────

    def seek_to_sequence(self, target_sequence: int) -> SeekResult:
        """Seek to the first frame with ``sequence >= target_sequence``."""
        self._ensure_open()
        result = seek_to_sequence(
            target_sequence,
            sequence_index=self._sequence_index,
            snapshot_index=self._snapshot_index,
            chunks=self._session.chunks,
            chunk_paths=self._session.chunk_paths,
            adapter=self._adapter,
            strict=self._config.strict_mode,
        )
        self._cursor = result.cursor
        return result

    def seek_to_timestamp(self, target_monotonic_ns: int) -> SeekResult:
        """Seek to the first frame with ``monotonic_ns >= target``."""
        self._ensure_open()
        result = seek_to_timestamp(
            target_monotonic_ns,
            sequence_index=self._sequence_index,
            snapshot_index=self._snapshot_index,
            chunks=self._session.chunks,
            chunk_paths=self._session.chunk_paths,
            adapter=self._adapter,
            strict=self._config.strict_mode,
        )
        self._cursor = result.cursor
        return result

    # ── snapshots ─────────────────────────────────────────────────

    def load_snapshot_at(self, sequence: int) -> SnapshotEntry | None:
        """Return the snapshot whose ``sequence_at_capture`` is the
        largest value ``<= sequence``, or ``None`` if no such
        snapshot exists."""
        self._ensure_open()
        return self._snapshot_index.nearest_at_or_before(sequence)

    def load_snapshot_payload_at(self, sequence: int) -> dict[str, Any] | None:
        """Convenience — :meth:`load_snapshot_at` + JSON load."""
        entry = self.load_snapshot_at(sequence)
        if entry is None:
            return None
        return load_snapshot_payload(entry)

    # ── state reconstruction ──────────────────────────────────────

    def reconstruct_state_at(
        self,
        target_sequence: int,
        *,
        reducer: Reducer = default_collecting_reducer,
    ) -> StateReconstructionResult:
        """Rebuild runtime state at ``target_sequence`` using the
        nearest snapshot + delta replay."""
        self._ensure_open()
        return reconstruct_state(
            target_sequence,
            sequence_index=self._sequence_index,
            snapshot_index=self._snapshot_index,
            chunks=self._session.chunks,
            chunk_paths=self._session.chunk_paths,
            adapter=self._adapter,
            reducer=reducer,
            strict=self._config.strict_mode,
        )

    # ── chunk health ──────────────────────────────────────────────

    def chunk_health(self) -> tuple[ChunkHealth, ...]:
        """Inspect every chunk's surface health without modifying it."""
        self._ensure_open()
        return tuple(
            inspect_chunk(record, path)
            for record, path in zip(
                self._session.chunks, self._session.chunk_paths, strict=True,
            )
        )

    # ── internals ─────────────────────────────────────────────────

    def _resolve_adapter(self) -> FrameAdapter:
        if self._config.frame_format == "auto":
            return detect_format_from_session(self._session.chunk_paths)
        return select_frame_adapter(self._config.frame_format)

    def _build_chunk_loaders(self) -> list[ReplayChunkLoader]:
        return [
            ReplayChunkLoader(
                record, path, adapter=self._adapter, strict=self._config.strict_mode,
            )
            for record, path in zip(
                self._session.chunks, self._session.chunk_paths, strict=True,
            )
        ]

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("replay loader is closed")


def _merge_cursor_window(window: ReplayWindow | None, cursor_start: int) -> ReplayWindow:
    """Combine an optional window with a cursor resume point. The
    resulting window's ``start_sequence`` is the max of the caller's
    bound and ``cursor_start``, so iteration always honors both."""
    if window is None:
        return ReplayWindow(start_sequence=cursor_start) if cursor_start > 0 else ReplayWindow()
    if cursor_start <= window.start_sequence:
        return window
    return ReplayWindow(
        start_sequence=cursor_start,
        end_sequence=window.end_sequence,
        start_monotonic_ns=window.start_monotonic_ns,
        end_monotonic_ns=window.end_monotonic_ns,
    )
