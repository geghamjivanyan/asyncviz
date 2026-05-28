"""Canonical replay recorder facade.

Wires together the queue, the writer, the worker thread, and the
snapshot capture. Lifecycle is straightforward:

  recorder = ReplayRecorder(config, state_store=...)
  recorder.start(meta_provider=...)         # boots the worker thread
  ...                                       # user's program runs
  recorder.stop()                           # flushes + finalizes the bundle

``stop()`` is idempotent + safe to call from a signal handler. The
recorder never raises into the runtime — every callback path catches
and reports through the writer's error counters + the recorder
tracing ring.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from asyncviz.runtime.replay.artifacts.replay_layout import (
    RUNTIME_SNAPSHOT_FILENAME,
    SNAPSHOT_DIRECTORY,
    WARNINGS_SNAPSHOT_FILENAME,
)
from asyncviz.runtime.replay.frames import ReplayFrame, frame_from_event
from asyncviz.runtime.replay.recorder.replay_backpressure import (
    BoundedRecordQueue,
)
from asyncviz.runtime.replay.recorder.replay_chunking import ChunkPolicy
from asyncviz.runtime.replay.recorder.replay_configuration import RecorderConfig
from asyncviz.runtime.replay.recorder.replay_integrity import (
    atomic_write_text,
    finalize_marker,
    open_marker,
)
from asyncviz.runtime.replay.recorder.replay_manifest import (
    build_manifest,
    write_manifest,
)
from asyncviz.runtime.replay.recorder.replay_metadata import (
    PackagingMeta,
    RecorderMeta,
    RuntimeMeta,
    write_meta,
)
from asyncviz.runtime.replay.recorder.replay_metrics import get_recorder_metrics
from asyncviz.runtime.replay.recorder.replay_serializer import serialize_frame
from asyncviz.runtime.replay.recorder.replay_statistics import RecordingStatistics
from asyncviz.runtime.replay.recorder.replay_tracing import record_recorder_trace
from asyncviz.runtime.replay.recorder.replay_writer import ReplayWriter

# Type aliases for the meta providers passed at start() time. The
# recorder doesn't import these subsystems directly to keep the import
# graph thin — the caller is responsible for stitching them together.
RuntimeMetaProvider = Callable[[], RuntimeMeta]
PackagingMetaProvider = Callable[[], PackagingMeta | None]
SnapshotProvider = Callable[[], dict | None]


class ReplayRecorder:
    """Background recorder that turns the state-store stream into a bundle."""

    def __init__(
        self,
        config: RecorderConfig,
        *,
        state_store: object,
    ) -> None:
        self.config = config
        self._state_store = state_store
        self._queue = BoundedRecordQueue(
            capacity=config.queue_capacity,
            mode=config.backpressure,
        )
        self._writer = ReplayWriter(
            bundle_dir=config.output_path,
            compression=config.compression,
            chunk_policy=ChunkPolicy(
                max_events=config.chunk_events,
                max_bytes=config.chunk_bytes,
            ),
        )
        self._stats = RecordingStatistics()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._subscription = None  # store-specific subscription handle.
        self._started = False
        self._stopped = False
        self._lock = threading.Lock()
        self._meta_runtime: RuntimeMetaProvider | None = None
        self._meta_packaging: PackagingMetaProvider | None = None
        self._snapshot_runtime: SnapshotProvider | None = None
        self._snapshot_warnings: SnapshotProvider | None = None

    @property
    def output_path(self) -> Path:
        return self.config.output_path

    @property
    def statistics(self) -> RecordingStatistics:
        return self._stats

    def start(
        self,
        *,
        runtime_meta: RuntimeMetaProvider,
        packaging_meta: PackagingMetaProvider | None = None,
        runtime_snapshot: SnapshotProvider | None = None,
        warning_snapshot: SnapshotProvider | None = None,
    ) -> None:
        """Open the bundle + start the worker thread + subscribe to events."""
        with self._lock:
            if self._started:
                return
            self._started = True
        self.config.output_path.mkdir(parents=True, exist_ok=True)
        open_marker(self.config.output_path)
        get_recorder_metrics().record_session_started()
        record_recorder_trace("session-started", str(self.config.output_path))

        self._meta_runtime = runtime_meta
        self._meta_packaging = packaging_meta
        self._snapshot_runtime = runtime_snapshot
        self._snapshot_warnings = warning_snapshot

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="asyncviz-replay-recorder",
            daemon=True,
        )
        self._worker.start()

        subscribe = getattr(self._state_store, "subscribe", None)
        if callable(subscribe):
            self._subscription = subscribe(self._on_state_change)

    def stop(self, *, timeout: float = 5.0) -> None:
        """Flush + close the bundle. Idempotent + safe from signal handlers."""
        with self._lock:
            if self._stopped:
                return
            self._stopped = True

        # Detach the subscription first so no new events arrive
        # mid-shutdown.
        if self._subscription is not None:
            unsubscribe = getattr(self._state_store, "unsubscribe", None)
            if callable(unsubscribe):
                import contextlib

                with contextlib.suppress(Exception):  # pragma: no cover — best-effort
                    unsubscribe(self._subscription)
            self._subscription = None

        self._stop_event.set()
        self._queue.wake()
        if self._worker is not None:
            self._worker.join(timeout=timeout)

        # Drain anything the worker couldn't pull before the stop event.
        self._drain_remaining()

        finalized_cleanly = True
        try:
            self._writer.close()
        except Exception:  # pragma: no cover — best-effort
            finalized_cleanly = False
            get_recorder_metrics().record_writer_error()
            self._stats.record_writer_error()

        # Capture final snapshots after the writer is closed so the
        # snapshot files reflect a quiescent runtime.
        self._capture_snapshots()
        self._write_metadata_and_manifest(finalized=finalized_cleanly)

        # Record session-final metrics.
        for chunk in self._writer.finalized_chunks:
            self._stats.record_chunk_finalized(bytes_on_disk=chunk.compressed_bytes)
            get_recorder_metrics().record_chunk(bytes_written=chunk.compressed_bytes)

        self._stats.mark_finished(cleanly=finalized_cleanly)
        if finalized_cleanly:
            finalize_marker(self.config.output_path)
            get_recorder_metrics().record_session_finalized(
                duration_seconds=self._stats.duration_seconds,
            )
            record_recorder_trace("session-finalized", str(self.config.output_path))
        else:
            get_recorder_metrics().record_session_aborted(
                duration_seconds=self._stats.duration_seconds,
            )
            record_recorder_trace("session-aborted", str(self.config.output_path))

    # ── hot path ──────────────────────────────────────────────────────

    def _on_state_change(self, change: object) -> None:
        # Conservative: we never want a recorder bug to crash the
        # runtime. Every step is wrapped.
        try:
            sequence = getattr(change, "sequence", None)
            event = getattr(change, "event", None)
            if sequence is None or event is None:
                return
            self._stats.record_event_seen()
            event_type = getattr(event, "event_type", "")
            if not self.config.filter_allows(event_type):
                self._stats.record_event_filtered()
                get_recorder_metrics().record_events(filtered=1)
                record_recorder_trace("event-filtered", event_type)
                return
            frame = frame_from_event(event, sequence=int(sequence))
            payload = serialize_frame(frame)
            outcome = self._queue.offer((frame, payload))
            if not outcome.accepted:
                self._stats.record_event_dropped()
                get_recorder_metrics().record_events(dropped=1)
                record_recorder_trace("event-dropped", f"seq={sequence}")
            elif outcome.dropped_was_oldest:
                self._stats.record_event_dropped()
                get_recorder_metrics().record_events(dropped=1)
                record_recorder_trace("event-dropped", "evicted-oldest")
        except Exception:  # pragma: no cover — defensive
            get_recorder_metrics().record_writer_error()
            self._stats.record_writer_error()

    def _worker_loop(self) -> None:
        flush_interval = max(0.05, self.config.flush_interval_seconds)
        last_flush = time.monotonic()
        while not self._stop_event.is_set():
            if not self._queue.wait_for_item(flush_interval):
                self._do_flush()
                last_flush = time.monotonic()
                continue
            self._drain_once()
            if time.monotonic() - last_flush >= flush_interval:
                self._do_flush()
                last_flush = time.monotonic()
        # Stop event fired — drain the queue one last time.
        self._drain_once()
        self._do_flush()

    def _drain_once(self) -> None:
        records = self._queue.drain(max_items=1024)
        for record in records:
            self._consume_record(record)

    def _drain_remaining(self) -> None:
        # Called after the worker has joined; drain whatever's left.
        while True:
            records = self._queue.drain(max_items=1024)
            if not records:
                return
            for record in records:
                self._consume_record(record)

    def _consume_record(self, record: object) -> None:
        frame: ReplayFrame
        payload: bytes
        try:
            frame, payload = record  # type: ignore[misc]
        except Exception:  # pragma: no cover
            return
        try:
            self._writer.write_record(sequence=frame.sequence, payload=payload)
            self._stats.record_event_recorded(
                sequence=frame.sequence,
                payload_size=len(payload),
            )
            get_recorder_metrics().record_events(recorded=1)
        except Exception:
            self._stats.record_writer_error()
            get_recorder_metrics().record_writer_error()
            record_recorder_trace("writer-error", f"seq={frame.sequence}")

    def _do_flush(self) -> None:
        try:
            self._writer.flush()
            self._stats.record_flush()
            get_recorder_metrics().record_flush()
            record_recorder_trace("flush", "")
        except Exception:  # pragma: no cover — defensive
            self._stats.record_writer_error()
            get_recorder_metrics().record_writer_error()

    # ── shutdown helpers ──────────────────────────────────────────────

    def _capture_snapshots(self) -> None:
        snap_dir = self.config.output_path / SNAPSHOT_DIRECTORY
        snap_dir.mkdir(parents=True, exist_ok=True)
        if self.config.capture_runtime_snapshot and self._snapshot_runtime is not None:
            try:
                payload = self._snapshot_runtime()
            except Exception:
                payload = None
            if payload is not None:
                atomic_write_text(
                    snap_dir / RUNTIME_SNAPSHOT_FILENAME,
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
                )
                record_recorder_trace("snapshot-written", RUNTIME_SNAPSHOT_FILENAME)
        if self.config.capture_warning_snapshot and self._snapshot_warnings is not None:
            try:
                payload = self._snapshot_warnings()
            except Exception:
                payload = None
            if payload is not None:
                atomic_write_text(
                    snap_dir / WARNINGS_SNAPSHOT_FILENAME,
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
                )
                record_recorder_trace("snapshot-written", WARNINGS_SNAPSHOT_FILENAME)

    def _write_metadata_and_manifest(self, *, finalized: bool) -> None:
        runtime_meta: RuntimeMeta | None = None
        if self._meta_runtime is not None:
            try:
                runtime_meta = self._meta_runtime()
            except Exception:  # pragma: no cover — best-effort
                runtime_meta = None
        if runtime_meta is None:
            runtime_meta = RuntimeMeta(
                runtime_id="unknown",
                asyncviz_version="unknown",
                started_at_wall_iso="",
                finished_at_wall_iso=None,
                started_at_monotonic_ns=0,
                finished_at_monotonic_ns=None,
                host="",
                port=0,
                target={},
            )

        packaging_meta: PackagingMeta | None = None
        if self._meta_packaging is not None:
            try:
                packaging_meta = self._meta_packaging()
            except Exception:  # pragma: no cover
                packaging_meta = None

        recorder_meta = RecorderMeta(
            config={
                "output_path": str(self.config.output_path),
                "compression": self.config.compression.value,
                "chunk_events": self.config.chunk_events,
                "chunk_bytes": self.config.chunk_bytes,
                "queue_capacity": self.config.queue_capacity,
                "backpressure": self.config.backpressure.value,
                "flush_interval_seconds": self.config.flush_interval_seconds,
                "capture_runtime_snapshot": self.config.capture_runtime_snapshot,
                "capture_warning_snapshot": self.config.capture_warning_snapshot,
                "include_event_types": list(self.config.include_event_types)
                if self.config.include_event_types is not None
                else None,
                "exclude_event_types": list(self.config.exclude_event_types),
                "metadata_overrides": [list(p) for p in self.config.metadata_overrides],
            },
            statistics=self._stats.to_dict(),
            metrics=asdict(get_recorder_metrics().snapshot()),
        )

        write_meta(
            self.config.output_path,
            runtime=runtime_meta,
            packaging=packaging_meta,
            recorder=recorder_meta,
        )

        manifest = build_manifest(
            asyncviz_version=runtime_meta.asyncviz_version or "unknown",
            runtime_id=runtime_meta.runtime_id,
            bundle_id=str(uuid.uuid4()),
            created_at_iso=datetime.now(UTC).isoformat(timespec="seconds"),
            finalized=finalized,
            chunks=self._writer.finalized_chunks,
            snapshot_files=self._snapshot_files_index(),
            meta_files=self._meta_files_index(),
            extras=dict(self.config.metadata_overrides),
        )
        write_manifest(self.config.output_path, manifest)

    def _snapshot_files_index(self) -> dict[str, str]:
        out: dict[str, str] = {}
        snap_dir = self.config.output_path / SNAPSHOT_DIRECTORY
        if (snap_dir / RUNTIME_SNAPSHOT_FILENAME).is_file():
            out["runtime"] = f"{SNAPSHOT_DIRECTORY}/{RUNTIME_SNAPSHOT_FILENAME}"
        if (snap_dir / WARNINGS_SNAPSHOT_FILENAME).is_file():
            out["warnings"] = f"{SNAPSHOT_DIRECTORY}/{WARNINGS_SNAPSHOT_FILENAME}"
        return out

    def _meta_files_index(self) -> dict[str, str]:
        from asyncviz.runtime.replay.artifacts.replay_layout import (
            META_DIRECTORY,
            PACKAGING_META_FILENAME,
            RECORDER_META_FILENAME,
            RUNTIME_META_FILENAME,
        )

        out: dict[str, str] = {}
        meta_dir = self.config.output_path / META_DIRECTORY
        if (meta_dir / RUNTIME_META_FILENAME).is_file():
            out["runtime"] = f"{META_DIRECTORY}/{RUNTIME_META_FILENAME}"
        if (meta_dir / PACKAGING_META_FILENAME).is_file():
            out["packaging"] = f"{META_DIRECTORY}/{PACKAGING_META_FILENAME}"
        if (meta_dir / RECORDER_META_FILENAME).is_file():
            out["recorder"] = f"{META_DIRECTORY}/{RECORDER_META_FILENAME}"
        return out
