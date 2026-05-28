"""Per-line frame adapters.

Two on-disk frame shapes exist in the wild right now:

1. The canonical NDJSON wire format introduced in Task 9.2 — every
   line is a versioned :class:`ReplayFrame` envelope.
2. The recorder's pre-9.2 legacy format — flat object with
   ``sequence`` / ``event_id`` / ``event_type`` / ``monotonic_ns`` /
   ``payload`` keys. Existing recordings on disk still use this.

A :class:`FrameAdapter` knows how to turn one NDJSON line into a
:class:`ReplayFrame`. The loader is parameterized by an adapter so
the same iteration code paths work against both formats without
branching at the use sites. The :class:`AutoDetectFrameAdapter` is
the default — it sniffs the first non-empty line, commits to one
interpretation, and reuses it for the rest of the session.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from asyncviz.replay.format import (
    SCHEMA_VERSION,
    FrameDecodingError,
    ReplayFrame,
    decode_frame,
)
from asyncviz.replay.loading.replay_configuration import FrameFormat


class FrameAdapterError(ValueError):
    """Raised when an adapter cannot turn a line into a frame."""


@runtime_checkable
class FrameAdapter(Protocol):
    """Adapter contract — one method, in and out."""

    def decode_line(self, line: str) -> ReplayFrame: ...

    @property
    def format_name(self) -> str: ...


class CanonicalFrameAdapter:
    """The default for recordings written by the canonical format."""

    format_name: str = "canonical"

    def decode_line(self, line: str) -> ReplayFrame:
        try:
            return decode_frame(line)
        except FrameDecodingError as exc:
            raise FrameAdapterError(str(exc)) from exc


class LegacyRecordingFrameAdapter:
    """Adapter for the recorder's pre-9.2 frame format.

    Maps the recorder's flat dict into a canonical
    :class:`ReplayFrame` so downstream code only ever speaks the new
    envelope shape. The legacy frame carries no
    ``runtime_id``/``recording_id``/``wall_time_ns`` — those land as
    ``None`` and the consumer is expected to look them up via the
    manifest if needed.
    """

    format_name: str = "legacy_recording"

    def decode_line(self, line: str) -> ReplayFrame:
        stripped = line.strip()
        if not stripped:
            raise FrameAdapterError("blank line")
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise FrameAdapterError(f"malformed JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise FrameAdapterError("frame must be a JSON object")
        if "sequence" not in data or "event_type" not in data:
            raise FrameAdapterError("legacy frame missing 'sequence' or 'event_type'")
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        return ReplayFrame(
            schema_version=SCHEMA_VERSION,
            frame_type="runtime_event",
            sequence=int(data["sequence"]),
            monotonic_ns=int(data.get("monotonic_ns", 0)),
            payload_type=str(data["event_type"]),
            payload=payload,
            wall_time_ns=None,
        )


class AutoDetectFrameAdapter:
    """Sniff the first line, then delegate.

    The check is cheap — we only inspect the top-level dict for
    ``schema_version``. Anything else (including malformed JSON)
    falls back to the legacy adapter, which itself raises a clean
    ``FrameAdapterError`` if the line is unrecognizable.
    """

    format_name: str = "auto"

    def __init__(self) -> None:
        self._inner: FrameAdapter | None = None

    @property
    def selected(self) -> FrameAdapter | None:
        return self._inner

    def decode_line(self, line: str) -> ReplayFrame:
        if self._inner is None:
            self._inner = self._sniff(line)
        return self._inner.decode_line(line)

    @staticmethod
    def _sniff(line: str) -> FrameAdapter:
        stripped = line.strip()
        if not stripped:
            # Empty first line — assume legacy and let the next line
            # tell us for sure.
            return LegacyRecordingFrameAdapter()
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return LegacyRecordingFrameAdapter()
        if isinstance(data, dict) and "schema_version" in data and "frame_type" in data:
            return CanonicalFrameAdapter()
        return LegacyRecordingFrameAdapter()


def select_frame_adapter(frame_format: FrameFormat) -> FrameAdapter:
    """Return the adapter matching the configured frame format."""
    if frame_format == "canonical":
        return CanonicalFrameAdapter()
    if frame_format == "legacy_recording":
        return LegacyRecordingFrameAdapter()
    return AutoDetectFrameAdapter()
