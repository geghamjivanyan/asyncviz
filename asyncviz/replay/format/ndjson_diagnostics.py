"""Diagnostics builder for the replay format layer.

One call → one snapshot containing everything the diagnostics page
needs: metric counters, recent trace entries, registered codec /
migration inventories, and the active schema/protocol versions.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.format.ndjson_observability import (
    NdjsonFormatMetricsSnapshot,
    get_format_metrics_snapshot,
)
from asyncviz.replay.format.ndjson_registry import get_payload_registry
from asyncviz.replay.format.ndjson_schema import (
    ALL_FRAME_TYPES,
    MIN_READABLE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
)
from asyncviz.replay.format.ndjson_tracing import (
    NdjsonTraceEntry,
    get_ndjson_trace,
    is_ndjson_trace_enabled,
)
from asyncviz.replay.format.ndjson_versioning import get_migration_registry


@dataclass(frozen=True, slots=True)
class NdjsonFormatDiagnostics:
    """Compact view of the format layer's runtime state."""

    schema_version: int
    min_readable_schema_version: int
    protocol_version: int
    known_frame_types: tuple[str, ...]
    registered_payload_types: tuple[str, ...]
    migration_steps: tuple[str, ...]
    metrics: NdjsonFormatMetricsSnapshot
    trace_enabled: bool
    recent_trace: tuple[NdjsonTraceEntry, ...]


def build_format_diagnostics(*, trace_limit: int = 32) -> NdjsonFormatDiagnostics:
    """Collect the live diagnostics view. ``trace_limit`` caps the
    trace tail returned so the diagnostics page doesn't have to scan
    the whole ring on every refresh."""
    trace = get_ndjson_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    migration_steps = tuple(
        f"{key.payload_type}:{key.from_version}->{key.to_version}"
        for key in get_migration_registry().known_steps()
    )
    return NdjsonFormatDiagnostics(
        schema_version=SCHEMA_VERSION,
        min_readable_schema_version=MIN_READABLE_SCHEMA_VERSION,
        protocol_version=PROTOCOL_VERSION,
        known_frame_types=ALL_FRAME_TYPES,
        registered_payload_types=get_payload_registry().known_types(),
        migration_steps=migration_steps,
        metrics=get_format_metrics_snapshot(),
        trace_enabled=is_ndjson_trace_enabled(),
        recent_trace=trace,
    )
