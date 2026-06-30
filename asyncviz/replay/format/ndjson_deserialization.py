"""NDJSON line → frame decoder.

The decoder is the *first* place untrusted bytes touch the replay
format, so it's deliberately strict-by-construction but lenient by
default: malformed lines are isolated and reported, not allowed to
crash the replay stream. The two extremes that show up in real
recordings are:

* a torn last line from a crashed writer — handled by the recovery
  layer which truncates before decode is even attempted, but the
  decoder still guards in case something slips through.
* a frame from a *newer* producer carrying additive envelope fields
  — handled by routing unknown keys into ``ReplayFrame.extensions``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_observability import get_format_metrics
from asyncviz.replay.format.ndjson_registry import get_payload_registry
from asyncviz.replay.format.ndjson_schema import SCHEMA_VERSION
from asyncviz.replay.format.ndjson_tracing import record_ndjson_trace
from asyncviz.replay.format.ndjson_versioning import (
    check_envelope_compatibility,
    get_migration_registry,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("replay.format.deserializer")


class FrameDecodingError(ValueError):
    """Raised when an NDJSON line cannot be decoded into a frame."""


def decode_frame(line: str | bytes) -> ReplayFrame:
    """Decode one NDJSON line into a :class:`ReplayFrame`.

    Raises :class:`FrameDecodingError` if the line is malformed.
    Counters and tracing fire on both success + failure so format
    health is visible without enabling debug logging.
    """
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            get_format_metrics().record_malformed_frame()
            record_ndjson_trace("frame-skipped", f"utf8={exc}")
            raise FrameDecodingError(f"line not valid UTF-8: {exc}") from exc

    stripped = line.strip()
    if not stripped:
        get_format_metrics().record_malformed_frame()
        record_ndjson_trace("frame-skipped", "blank line")
        raise FrameDecodingError("blank line")

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        get_format_metrics().record_malformed_frame()
        record_ndjson_trace("frame-skipped", f"json={exc}")
        raise FrameDecodingError(f"malformed JSON: {exc}") from exc

    if not isinstance(data, dict):
        get_format_metrics().record_malformed_frame()
        record_ndjson_trace("frame-skipped", "not-an-object")
        raise FrameDecodingError(f"frame must be a JSON object, got {type(data).__name__}")

    envelope_version = data.get("schema_version")
    if not isinstance(envelope_version, int):
        get_format_metrics().record_malformed_frame()
        record_ndjson_trace("frame-skipped", "missing-schema-version")
        raise FrameDecodingError("missing or non-int schema_version")

    verdict = check_envelope_compatibility(envelope_version)
    if not verdict.compatible:
        get_format_metrics().record_validation_failure()
        record_ndjson_trace("validation-failed", verdict.reason)
        raise FrameDecodingError(verdict.reason)
    if envelope_version != SCHEMA_VERSION:
        get_format_metrics().record_schema_skew()
        record_ndjson_trace(
            "schema-skew",
            f"decode frame={envelope_version} reader={SCHEMA_VERSION}",
        )

    try:
        frame = ReplayFrame.from_dict(data)
    except ValueError as exc:
        get_format_metrics().record_malformed_frame()
        record_ndjson_trace("frame-skipped", str(exc))
        raise FrameDecodingError(str(exc)) from exc

    get_format_metrics().record_frame_decoded(len(stripped))
    record_ndjson_trace(
        "frame-decoded",
        f"seq={frame.sequence} type={frame.frame_type}",
    )
    return frame


def decode_payload(frame: ReplayFrame) -> Any:
    """Run the registry decoder on a frame's payload. If no codec is
    registered, returns the raw payload dict so the caller still has
    something useful."""
    codec = get_payload_registry().get(frame.payload_type)
    if codec is None:
        return frame.payload
    try:
        return codec.decode(frame.payload)
    except Exception as exc:  # defensive — codecs are user-supplied
        logger.debug(
            "payload decode for %s failed (%s) — returning raw dict",
            frame.payload_type,
            exc,
        )
        get_format_metrics().record_validation_failure()
        record_ndjson_trace("validation-failed", f"payload={frame.payload_type} err={exc}")
        return frame.payload


def migrate_payload(frame: ReplayFrame, *, from_version: int, to_version: int) -> ReplayFrame:
    """Walk a frame's payload through registered migrations and
    return a new frame whose payload reflects ``to_version``."""
    if from_version == to_version:
        return frame
    migrated = get_migration_registry().migrate(
        frame.payload_type,
        frame.payload,
        from_version=from_version,
        to_version=to_version,
    )
    if migrated is frame.payload:
        return frame
    get_format_metrics().record_migration_applied()
    record_ndjson_trace(
        "migration-applied",
        f"type={frame.payload_type} {from_version}->{to_version}",
    )
    return ReplayFrame(
        schema_version=frame.schema_version,
        frame_type=frame.frame_type,
        sequence=frame.sequence,
        monotonic_ns=frame.monotonic_ns,
        payload_type=frame.payload_type,
        payload=migrated,
        runtime_id=frame.runtime_id,
        recording_id=frame.recording_id,
        wall_time_ns=frame.wall_time_ns,
        extensions=frame.extensions,
    )


def iter_decode_lines(
    lines: Iterable[str | bytes],
    *,
    strict: bool = False,
) -> Iterator[ReplayFrame]:
    """Decode an iterable of lines into frames.

    With ``strict=False`` (default), malformed lines are skipped and
    counted as malformed_frames — the caller's iteration continues.
    With ``strict=True``, the first decoding error halts iteration.
    """
    for raw in lines:
        try:
            yield decode_frame(raw)
        except FrameDecodingError:
            if strict:
                raise
            continue
