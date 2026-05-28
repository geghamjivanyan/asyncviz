"""Frame → NDJSON line encoder.

One serialized line == one frame == ``encoded_dict + "\\n"``. The
encoder is intentionally minimal: route through the canonical JSON
codec so the bytes are stable across runs, and observe one set of
counters so format health is always queryable.

Keep this layer pure of file IO. The writer in :mod:`ndjson_writer`
owns the file handle; this module only converts in-memory objects to
bytes.
"""

from __future__ import annotations

from typing import Any

from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_observability import get_format_metrics
from asyncviz.replay.format.ndjson_registry import get_payload_registry
from asyncviz.replay.format.ndjson_schema import SCHEMA_VERSION, FrameType
from asyncviz.replay.format.ndjson_tracing import record_ndjson_trace
from asyncviz.replay.format.utils.canonical_json import (
    CanonicalEncodingError,
    canonical_dumps,
    sort_mapping,
)

_LINE_TERMINATOR = "\n"


class FrameEncodingError(ValueError):
    """Raised when a frame cannot be serialized deterministically."""


def encode_frame(frame: ReplayFrame) -> str:
    """Serialize one frame to a single NDJSON line (incl. trailing
    ``\\n``)."""
    if frame.schema_version != SCHEMA_VERSION:
        # Allowed in principle (older producers shouldn't be common),
        # but we record the skew so it shows up in diagnostics.
        get_format_metrics().record_schema_skew()
        record_ndjson_trace(
            "schema-skew",
            f"encode frame schema={frame.schema_version} reader={SCHEMA_VERSION}",
        )
    data = frame.to_dict()
    try:
        line = canonical_dumps(sort_mapping(data)) + _LINE_TERMINATOR
    except CanonicalEncodingError as exc:
        raise FrameEncodingError(f"frame {frame.sequence} not encodable: {exc}") from exc
    encoded_bytes = len(line.encode("utf-8"))
    get_format_metrics().record_frame_encoded(encoded_bytes)
    record_ndjson_trace(
        "frame-encoded",
        f"seq={frame.sequence} type={frame.frame_type} bytes={encoded_bytes}",
    )
    return line


def encode_payload(
    payload_type: str,
    payload: Any,
) -> dict[str, Any]:
    """Run a domain object through the registry's encode hook, falling
    back to a pass-through if no codec is registered."""
    codec = get_payload_registry().get(payload_type)
    if codec is None:
        if isinstance(payload, dict):
            return payload
        return {"value": payload}
    return codec.encode(payload)


def build_frame(
    *,
    frame_type: FrameType,
    sequence: int,
    monotonic_ns: int,
    payload_type: str,
    payload: Any,
    runtime_id: str | None = None,
    recording_id: str | None = None,
    wall_time_ns: int | None = None,
) -> ReplayFrame:
    """Single-step factory: encode a payload + wrap it in an envelope.

    Use this when the caller has a domain object (e.g. a
    ``RuntimeEvent``) and wants a ``ReplayFrame`` in one call.
    """
    encoded_payload = encode_payload(payload_type, payload)
    return ReplayFrame(
        schema_version=SCHEMA_VERSION,
        frame_type=frame_type,
        sequence=sequence,
        monotonic_ns=monotonic_ns,
        payload_type=payload_type,
        payload=encoded_payload,
        runtime_id=runtime_id,
        recording_id=recording_id,
        wall_time_ns=wall_time_ns,
    )
