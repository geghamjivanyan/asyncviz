"""Canonical runtime recorder.

Wires together:

* the bus subscription (consumes every ``RuntimeEvent`` flowing through
  :class:`asyncviz.runtime.events.EventBus`)
* the per-event sequence allocator
* the bounded buffer + background writer worker
* the manifest + index persistence
* optional snapshot capture at session boundaries

Lifecycle::

    recorder = RuntimeRecorder(config=cfg, bus=bus)
    recorder.start()
    ...                                # runtime emits events
    recorder.append_snapshot(...)      # optional checkpoint
    recorder.stop()                    # flushes + finalizes the bundle

``stop()`` is idempotent and safe to call from a signal handler. The
recorder never raises into the runtime — every callback path catches
and reports through the writer's error counters + the recorder
tracing ring.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from asyncviz.packaging import package_version
from asyncviz.replay.recording.recording_configuration import RecordingConfig
from asyncviz.replay.recording.recording_index import (
    build_index_from_chunks,
    write_index,
)
from asyncviz.replay.recording.recording_layout import (
    SCHEMA_VERSION,
    snapshot_chunk_path,
    snapshots_dir,
)
from asyncviz.replay.recording.recording_manifest import write_manifest
from asyncviz.replay.recording.recording_metadata import (
    RecordingMetadata,
    SnapshotRecord,
)
from asyncviz.replay.recording.recording_observability import get_recording_metrics
from asyncviz.replay.recording.recording_paths import (
    ensure_directory,
    session_dir_for,
)
from asyncviz.replay.recording.recording_session import RecordingSession
from asyncviz.replay.recording.recording_tracing import record_recording_trace
from asyncviz.replay.recording.recording_writer import RecordingWriter
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import to_dict
from asyncviz.utils.logging import get_logger

logger = get_logger("replay.recording.runtime_recorder")


# Re-entrancy guard: the recorder calls ``bus.publish`` only when an
# external API requests it (none today, but kept for symmetry with the
# instrumentation patchers). If a future emit path triggers another
# event back into the recorder, this guard prevents a self-amplification
# loop.
_in_recorder = threading.local()


def _begin_recorder() -> bool:
    if getattr(_in_recorder, "active", False):
        return False
    _in_recorder.active = True
    return True


def _end_recorder() -> None:
    _in_recorder.active = False


class RuntimeRecorder:
    """Append-oriented runtime event recorder."""

    def __init__(
        self,
        *,
        config: RecordingConfig,
        bus: EventBus | None = None,
        snapshot_provider: callable | None = None,  # type: ignore[valid-type]
        recording_id: str | None = None,
        runtime_id: str | None = None,
    ) -> None:
        self._config = config
        self._bus = bus
        self._snapshot_provider = snapshot_provider
        self._lock = threading.RLock()
        self._session = RecordingSession.new(
            runtime_id=runtime_id,
            asyncviz_version=package_version(),
            recording_id=recording_id,
        )
        self._session_dir = session_dir_for(
            Path(config.root_dir), self._session.recording_id,
        )
        ensure_directory(self._session_dir)
        ensure_directory(snapshots_dir(self._session_dir))
        self._writer = RecordingWriter(self._session_dir, config=config)
        self._sequence_counter = itertools.count(1)
        self._bus_subscription: object | None = None
        self._snapshots: list[SnapshotRecord] = []
        self._metrics = get_recording_metrics()
        self._started = False

    # ── public lifecycle ──────────────────────────────────────────

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def session(self) -> RecordingSession:
        return self._session

    @property
    def session_dir(self) -> Path:
        return self._session_dir

    @property
    def config(self) -> RecordingConfig:
        return self._config

    def start(self) -> None:
        """Boot the worker + subscribe to the bus. Idempotent."""
        with self._lock:
            if self._started:
                return
            self._writer.start()
            if self._bus is not None:
                self._bus_subscription = self._bus.subscribe(self._on_bus_event)
            self._session.mark_started()
            self._metrics.record_session_started()
            record_recording_trace(
                "session-started",
                f"id={self._session.recording_id}",
            )
            if self._config.snapshot_on_start:
                self.append_snapshot(kind="start")
            self._started = True
            # Write the initial manifest so an external reader can
            # discover the in-progress recording before any events land.
            self._write_manifest_locked()

    def stop(self) -> None:
        """Drain the writer, capture a final snapshot, finalize the
        manifest. Idempotent."""
        with self._lock:
            if not self._started and self._session.state == "stopped":
                return
            self._session.mark_stopping()
            sub = self._bus_subscription
            self._bus_subscription = None
        if sub is not None and self._bus is not None:
            with contextlib.suppress(Exception):
                self._bus.unsubscribe(sub)  # type: ignore[arg-type]
        with self._lock:
            if self._config.snapshot_on_stop:
                self.append_snapshot(kind="stop")
            self._writer.stop()
            # Pick up any chunks the writer rotated during ``stop``.
            self._session.chunk_count = len(self._writer.chunks_completed)
            self._session.mark_stopped()
            self._metrics.record_session_stopped()
            self._write_manifest_locked(finalized=True)
            if self._config.enable_index:
                index = build_index_from_chunks(list(self._writer.chunks_completed))
                with contextlib.suppress(Exception):
                    write_index(self._session_dir, index)
            record_recording_trace(
                "session-stopped",
                f"id={self._session.recording_id} events={self._session.event_count}",
            )
            self._started = False

    # ── public append ─────────────────────────────────────────────

    def append_event(self, event: RuntimeEvent, *, sequence: int | None = None) -> int:
        """Manually append an event. Returns the assigned sequence.

        Called by the bus subscription internally; exposed publicly so
        tools that bypass the bus (replay-from-replay scenarios) can
        feed events into the recording directly."""
        if not _begin_recorder():
            self._metrics.record_recursion_skip()
            record_recording_trace("recursion-skip", "append_event")
            return -1
        try:
            assigned = sequence if sequence is not None else next(self._sequence_counter)
            payload = self._serialize_event(event, assigned)
            result = self._writer.enqueue(sequence=assigned, payload=payload)
            self._session.record_event(assigned)
            record_recording_trace(
                "event-appended",
                f"seq={assigned} action={result.action}",
            )
            return assigned
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("recorder append failed: %s", exc)
            return -1
        finally:
            _end_recorder()

    def append_snapshot(
        self,
        *,
        snapshot: dict[str, Any] | None = None,
        kind: str = "checkpoint",
    ) -> SnapshotRecord | None:
        """Capture a snapshot of runtime state into ``snapshots/``.

        ``snapshot`` may be provided directly or sourced from the
        configured ``snapshot_provider`` callable. Returns the
        :class:`SnapshotRecord` describing what was written, or
        ``None`` when no snapshot was available.
        """
        if snapshot is None and self._snapshot_provider is not None:
            try:
                snapshot = self._snapshot_provider()
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("snapshot provider failed: %s", exc)
                return None
        if snapshot is None:
            return None
        index = len(self._snapshots) + 1
        path = snapshot_chunk_path(self._session_dir, index)
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
        path.write_text(serialized, encoding="utf-8")
        record = SnapshotRecord(
            index=index,
            filename=path.name,
            sequence_at_capture=self._session.last_sequence,
            kind=kind,
            byte_size=path.stat().st_size,
        )
        self._snapshots.append(record)
        self._session.record_snapshot()
        self._metrics.record_snapshot_captured()
        record_recording_trace(
            "snapshot-captured", f"kind={kind} index={index}",
        )
        return record

    def flush(self) -> None:
        """Synchronously drain the writer + persist the manifest."""
        with self._lock:
            self._writer.flush()
            self._write_manifest_locked()

    # ── bus hook ──────────────────────────────────────────────────

    def _on_bus_event(self, event: RuntimeEvent) -> None:
        try:
            self.append_event(event)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("recorder bus callback failed: %s", exc)

    # ── helpers ───────────────────────────────────────────────────

    def _serialize_event(self, event: RuntimeEvent, sequence: int) -> dict[str, Any]:
        """Wrap the event in the canonical recording frame shape."""
        body = to_dict(event)
        return {
            "sequence": sequence,
            "event_id": str(getattr(event, "event_id", "")),
            "event_type": getattr(event, "event_type", ""),
            "monotonic_ns": int(getattr(event, "monotonic_ns", 0) or 0),
            "payload": body,
        }

    def _write_manifest_locked(self, *, finalized: bool = False) -> None:
        chunks = self._writer.chunks_completed
        current = self._writer.current_chunk_state
        all_chunks = list(chunks)
        if current is not None and current.event_count > 0:
            all_chunks.append(current)
        metadata = RecordingMetadata(
            schema_version=SCHEMA_VERSION,
            recording_id=self._session.recording_id,
            runtime_id=self._session.runtime_id,
            asyncviz_version=self._session.asyncviz_version,
            started_at_ns=self._session.started_at_ns,
            stopped_at_ns=self._session.stopped_at_ns,
            event_count=self._session.event_count,
            snapshot_count=self._session.snapshot_count,
            chunk_count=max(len(all_chunks), self._session.chunk_count),
            last_sequence=self._session.last_sequence,
            finalized=finalized,
            chunks=tuple(all_chunks),
            snapshots=tuple(self._snapshots),
            notes=dict(self._session.notes),
        )
        # Defensive: a manifest write failure must never crash recording.
        with contextlib.suppress(Exception):
            write_manifest(self._session_dir, metadata)

    # ── replay-from-stream convenience ────────────────────────────

    def append_events(self, events: Iterable[RuntimeEvent]) -> int:
        """Bulk-append helper. Returns the number of events accepted."""
        count = 0
        for event in events:
            if self.append_event(event) >= 0:
                count += 1
        return count
