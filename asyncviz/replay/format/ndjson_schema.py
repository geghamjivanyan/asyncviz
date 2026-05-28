"""Canonical schema constants for the NDJSON replay format.

The wire format is *envelope-versioned*: every line carries an
explicit ``schema_version`` so readers can tell whether they're being
asked to decode a frame they're old enough to understand. Payload
schemas (the runtime event protocol) evolve on a separate version
axis — :data:`PROTOCOL_VERSION` — exposed for migration logic but
deliberately decoupled from the envelope version.

Bumping :data:`SCHEMA_VERSION` is a wire-breaking change. Bumping the
payload protocol is not; reader migration logic in
:mod:`ndjson_versioning` knows how to upgrade payloads in-place.
"""

from __future__ import annotations

from typing import Final, Literal

from asyncviz.runtime.events.models.base import PROTOCOL_VERSION as _RUNTIME_PROTOCOL_VERSION

SCHEMA_VERSION: Final[int] = 1
"""Wire-envelope version. Every frame carries this. Bumped only when
the envelope shape changes in a way readers cannot tolerate."""

MIN_READABLE_SCHEMA_VERSION: Final[int] = 1
"""Oldest envelope version this reader will accept without explicit
migration logic. Frames below this are rejected as unreadable."""

PROTOCOL_VERSION: Final[int] = _RUNTIME_PROTOCOL_VERSION
"""Payload protocol version (the runtime event schema). Tracked
separately from envelope version so payloads can evolve additively
without breaking readers."""

FrameType = Literal[
    "runtime_event",
    "snapshot_begin",
    "snapshot_end",
    "snapshot_delta",
    "metadata",
    "diagnostics",
    "marker",
]
"""Closed set of frame kinds. New kinds bump :data:`SCHEMA_VERSION`."""

ALL_FRAME_TYPES: Final[tuple[FrameType, ...]] = (
    "runtime_event",
    "snapshot_begin",
    "snapshot_end",
    "snapshot_delta",
    "metadata",
    "diagnostics",
    "marker",
)

PayloadCategory = Literal["event", "snapshot", "metadata", "marker", "diagnostic"]
"""Coarse payload bucket — used by validators to dispatch."""

ENVELOPE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "frame_type",
        "sequence",
        "monotonic_ns",
        "wall_time_ns",
        "payload_type",
        "payload",
        "runtime_id",
        "recording_id",
        "extensions",
    },
)
"""Recognized top-level envelope keys. Unknown keys are *preserved*
under ``extensions`` to keep the format forward-compatible."""

REQUIRED_ENVELOPE_KEYS: Final[frozenset[str]] = frozenset(
    {"schema_version", "frame_type", "sequence", "monotonic_ns", "payload_type", "payload"},
)


def frame_type_category(frame_type: FrameType) -> PayloadCategory:
    """Bucket a frame type for validation dispatch."""
    if frame_type == "runtime_event":
        return "event"
    if frame_type in ("snapshot_begin", "snapshot_end", "snapshot_delta"):
        return "snapshot"
    if frame_type == "metadata":
        return "metadata"
    if frame_type == "marker":
        return "marker"
    return "diagnostic"
