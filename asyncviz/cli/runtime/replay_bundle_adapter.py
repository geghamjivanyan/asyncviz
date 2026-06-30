"""Adapter from the CLI recorder's bundle format → replay engine.

Background
----------
The codebase has two parallel replay-bundle implementations:

* :mod:`asyncviz.runtime.replay.recorder` (writer side) — owned by
  the live runtime + the ``asyncviz record`` CLI. Produces a bundle
  rooted at ``<name>.avz/`` with ``manifest.json`` keyed by
  ``bundle_id`` and per-chunk shape ``{file, event_count,
  compressed_bytes, sha256, sequence_start, sequence_end}``.

* :mod:`asyncviz.replay.loading` (reader side) — owned by the
  separate replay package. Expects a different manifest schema
  (``recording_id``, different chunk record shape).

The two were developed in parallel and never reconciled. For
``asyncviz replay`` to work against the bundles ``asyncviz record``
actually produces today, the launcher needs to read the recorder's
on-disk format and feed :class:`ReplayRuntimeEngine` directly.

This module is that adapter. It opens a recorder bundle via
:func:`asyncviz.runtime.replay.artifacts.open_bundle`, exposes the
narrow surface :class:`ReplayRuntimeEngine` consumes from a
loader (``snapshot_index`` + ``iter_frames`` + ``close``), and
translates the recorder's per-event JSON lines into canonical
:class:`ReplayFrame` objects.

Limitations of this adapter (intentional, v1 scope):

* Seek-by-sequence and snapshot-restore are not implemented — the
  recorder's snapshot files use a different on-disk shape than the
  loader's ``ReplaySnapshotIndex`` expects. ``snapshot_index`` is
  surfaced as an empty index so the engine constructs cleanly. The
  engine still routes play / pause / speed correctly; seek raises a
  NotImplementedError that the launcher can surface as a warning.

Once the recorder + loader manifest formats are reconciled this
adapter goes away — the launcher will just call
:meth:`ReplayEventLoader.open` directly.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from asyncviz.dashboard.replay.replay_marker_derivation import (
    derive_markers_and_bookmarks,
)
from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading.replay_snapshot_index import ReplaySnapshotIndex
from asyncviz.runtime.replay.artifacts.replay_bundle import (
    ReplayBundle,
    open_bundle,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("cli.runtime.replay_bundle_adapter")


@dataclass(frozen=True, slots=True)
class BundleSummary:
    """Operator-facing summary the launcher logs at startup."""

    bundle_id: str
    runtime_id: str | None
    event_count: int
    chunk_count: int
    snapshot_count: int
    last_sequence: int
    finalized: bool


class RecorderBundleAdapter:
    """Loader-shaped façade over a recorder-format ``.avz`` bundle.

    Quacks like enough of :class:`ReplayEventLoader` for
    :class:`ReplayRuntimeEngine` to construct + run playback. Anything
    the engine consumes (``snapshot_index``, ``iter_frames``, ``close``)
    is delegated or stubbed; anything the engine *would* consume only
    on seek (``reconstruct_state_at``) raises so misuse surfaces with a
    clear error.
    """

    __slots__ = ("_bundle", "_closed", "_snapshot_index")

    def __init__(self, bundle: ReplayBundle) -> None:
        self._bundle = bundle
        # No snapshots are exposed in v1 — the recorder writes its
        # snapshot files in a shape the loader's index doesn't yet
        # parse. The engine handles an empty index gracefully.
        self._snapshot_index = ReplaySnapshotIndex.from_records((), ())
        self._closed = False

    # ── construction helpers ─────────────────────────────────────────
    @staticmethod
    def open(bundle_dir: Path) -> RecorderBundleAdapter:
        """Open a recorder ``.avz`` bundle directory.

        Raises :class:`FileNotFoundError` when the manifest is absent
        — the launcher catches that and emits a user-facing error.
        """
        bundle = open_bundle(bundle_dir)
        return RecorderBundleAdapter(bundle)

    # ── loader-shaped surface (engine consumes these) ────────────────
    @property
    def snapshot_index(self) -> ReplaySnapshotIndex:
        return self._snapshot_index

    def iter_frames(self) -> Iterator[ReplayFrame]:
        """Yield one :class:`ReplayFrame` per recorded event.

        Recorder lines are flat dicts; we lift the runtime fields out
        and shape the rest as the canonical ``runtime_event`` frame
        payload (``{event_type, ...}``) the frontend reducer expects.
        """
        runtime_id = self._bundle.manifest.runtime_id
        recording_id = self._bundle.manifest.bundle_id
        for raw in self._bundle.iter_frames():
            event = _coerce_event_record(raw)
            if event is None:
                continue
            yield ReplayFrame.for_runtime_event(
                sequence=event.sequence,
                monotonic_ns=event.monotonic_ns,
                payload_type=event.event_type,
                payload=event.payload,
                runtime_id=runtime_id,
                recording_id=recording_id,
                wall_time_ns=event.wall_time_ns,
            )

    def close(self) -> None:
        """Idempotent close. The recorder bundle holds no open handles
        between iterations — this just flips an internal flag."""
        self._closed = True

    # ── degraded surfaces (seek/snapshot — not in v1 scope) ──────────
    def reconstruct_state_at(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError(
            "snapshot-based seek is not supported by the recorder bundle "
            "adapter yet — use play/pause/speed for now.",
        )

    # ── summary surface (used by the launcher banner) ────────────────
    def summary(self) -> BundleSummary:
        manifest = self._bundle.manifest
        return BundleSummary(
            bundle_id=manifest.bundle_id,
            runtime_id=manifest.runtime_id,
            event_count=manifest.event_count,
            chunk_count=len(manifest.chunks),
            snapshot_count=len(manifest.snapshot_files),
            last_sequence=manifest.last_sequence,
            finalized=manifest.finalized,
        )

    # ── timeline metadata (markers + bookmarks) ──────────────────────
    def derive_timeline_metadata(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        """Scan the recording once and return wire-shape markers + bookmarks.

        The scan is single-pass and pure, so it's safe to call once at
        launcher startup. Cost is proportional to event count; for the
        typical few-thousand-event recording it's a few ms.
        """
        return derive_markers_and_bookmarks(self._bundle.iter_frames())


# ── per-line coercion ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _CoercedEvent:
    sequence: int
    monotonic_ns: int
    event_type: str
    payload: dict[str, Any]
    wall_time_ns: int | None


def _coerce_event_record(raw: dict[str, Any]) -> _CoercedEvent | None:
    """Map a recorder JSON line to the engine's per-event shape.

    The recorder writes each event as a flat dict with the runtime
    envelope keys (``event_id``, ``event_type``, ``monotonic_ns``,
    ``payload``, ...). The engine needs a ``ReplayFrame`` carrying the
    canonical wire ``runtime_event`` payload — which is the SAME dict
    the live websocket bridge sends to the SPA. So we flatten the
    recorder's outer envelope back into the wire-shape payload.

    Returns ``None`` for malformed lines (no event_type / no sequence)
    — the caller silently skips them. The recorder is supposed to
    refuse to write malformed events, so a None here is best logged
    rather than raised.
    """
    event_type = raw.get("event_type")
    if not isinstance(event_type, str):
        return None
    monotonic_ns = raw.get("monotonic_ns")
    if not isinstance(monotonic_ns, int):
        return None
    # The recorder typically nests sequence inside the per-event dict
    # under ``sequence``; older recorders may put it on the payload.
    sequence = raw.get("sequence")
    if not isinstance(sequence, int):
        nested = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        sequence = nested.get("sequence") if isinstance(nested, dict) else None
    if not isinstance(sequence, int):
        # Fall back to a derived sequence — order of arrival from the
        # iterator is monotonic, so a counter on the iter_frames side
        # would work, but we surface None so the caller can decide.
        return None

    # Re-assemble the wire payload the SPA reducer expects: the
    # ``event_type`` discriminator at top level, plus the rest of the
    # recorder's payload dict. The recorder's outer fields
    # (``event_id``, ``monotonic_ns``, ``runtime_id``, etc.) are kept
    # in the payload so feature stores that read them still work.
    payload: dict[str, Any] = {"event_type": event_type}
    nested = raw.get("payload")
    if isinstance(nested, dict):
        payload.update(nested)
    # Recorder envelope fields that aren't already in the payload.
    for k in ("event_id", "runtime_id", "task_id", "parent_task_id"):
        if k in raw and k not in payload:
            payload[k] = raw[k]
    wall_time = raw.get("wall_time_ns")
    return _CoercedEvent(
        sequence=int(sequence),
        monotonic_ns=int(monotonic_ns),
        event_type=event_type,
        payload=payload,
        wall_time_ns=int(wall_time) if isinstance(wall_time, int) else None,
    )
