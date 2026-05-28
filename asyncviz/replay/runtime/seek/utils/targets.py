"""Target normalization helpers.

A :class:`SeekIntent` can be ``sequence`` / ``timestamp`` /
``marker`` / ``relative``; the coordinator needs a normalized
*sequence* to actually drive reconstruction. This module owns the
conversion.

Marker resolution is intentionally a callback because the
coordinator doesn't know about markers — those live in the UI
layer. Callers wire a resolver function (typically a dict lookup)
when constructing the coordinator.
"""

from __future__ import annotations

from collections.abc import Callable

from asyncviz.replay.loading import ReplayEventLoader
from asyncviz.replay.runtime.seek.models.seek_request import SeekIntent

MarkerResolver = Callable[[str], int]
"""``marker_id -> sequence``. Raises ``KeyError`` for unknown ids."""


class UnknownMarkerError(KeyError):
    """Raised by the default marker resolver when an id is unknown."""


def resolve_target_sequence(
    intent: SeekIntent,
    *,
    loader: ReplayEventLoader | None,
    current_cursor_sequence: int,
    marker_resolver: MarkerResolver | None = None,
) -> int:
    """Reduce an intent to its target sequence."""
    if intent.kind == "sequence":
        return max(0, intent.target_sequence)
    if intent.kind == "timestamp":
        if loader is None:
            raise ValueError(
                "timestamp seek requires a loader to look up sequence",
            )
        # Use the loader's seek logic to find the nearest frame ≥ ts.
        outcome = loader.seek_to_timestamp(intent.target_monotonic_ns)
        if outcome.landed_frame is not None:
            return outcome.landed_frame.sequence
        return current_cursor_sequence
    if intent.kind == "relative":
        return max(0, current_cursor_sequence + intent.relative_delta)
    if intent.kind == "marker":
        if marker_resolver is None:
            raise UnknownMarkerError(intent.marker_id)
        return marker_resolver(intent.marker_id)
    raise ValueError(f"unknown seek intent kind: {intent.kind!r}")
