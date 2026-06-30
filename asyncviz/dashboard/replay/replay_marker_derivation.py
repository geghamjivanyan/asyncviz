"""Derive replay-timeline markers + bookmarks from a recording's events.

The recorder captures the full runtime event stream into a bundle, but
the replay UI's timeline (scrubber pips, bookmarks list, density strip)
needs a narrow projection: one entry per *notable* event. Computing
that projection at recording time would require touching the recorder
write path. Computing it at bundle-open time instead keeps the writer
untouched and lets us iterate on the heuristics without re-recording
every session.

This module is the canonical derivation:

* :func:`derive_markers_and_bookmarks` — takes an iterable of
  recorder-shape event dicts (the same dicts ``ReplayBundle.iter_frames``
  yields) and returns ``(markers, bookmarks)`` arrays in the wire shape
  the replay broadcaster ships to the frontend.

The function is pure and side-effect free; tests exercise it without
touching disk.

Wire shapes — these mirror the frontend's
``ReplayTimelineMarker`` / ``ReplayBookmark`` types verbatim so the
broadcaster can pass them straight through:

::

    Marker = {
        "id": str,
        "kind": Literal[
            "warning", "saturation", "blocking",
            "checkpoint", "bookmark", "annotation",
        ],
        "severity": Literal["info", "warning", "critical"],
        "sequence": int,
        "monotonic_ns": int,
        "label": str,
        "description": str | None,  # absent when None
    }
    Bookmark = {
        "id": str,
        "label": str,
        "sequence": int,
        "monotonic_ns": int,
        "note": str | None,            # absent when None
        "created_at_ms": int,
    }
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Literal

MarkerKind = Literal[
    "warning",
    "saturation",
    "blocking",
    "checkpoint",
    "bookmark",
    "annotation",
]
MarkerSeverity = Literal["info", "warning", "critical"]


@dataclass(frozen=True, slots=True)
class _RawEvent:
    sequence: int
    monotonic_ns: int
    event_type: str
    payload: dict[str, Any]


def _coerce(raw: dict[str, Any]) -> _RawEvent | None:
    """Mirror the launcher's per-line coercion — drop malformed rows."""
    event_type = raw.get("event_type")
    if not isinstance(event_type, str):
        return None
    monotonic_ns = raw.get("monotonic_ns")
    if not isinstance(monotonic_ns, int):
        return None
    sequence = raw.get("sequence")
    if not isinstance(sequence, int):
        nested = raw.get("payload")
        if isinstance(nested, dict):
            sequence = nested.get("sequence")
    if not isinstance(sequence, int):
        return None
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    return _RawEvent(
        sequence=sequence,
        monotonic_ns=monotonic_ns,
        event_type=event_type,
        payload=payload,
    )


# ── per-event classification ──────────────────────────────────────────


def _classify(event: _RawEvent) -> tuple[MarkerKind, MarkerSeverity, str, str | None] | None:
    """Return ``(kind, severity, label, description)`` or None.

    ``None`` means the event isn't marker-worthy — most events fall
    into this bucket. Recording sizes are large; we deliberately only
    surface event types operators actually navigate to.
    """
    et = event.event_type
    p = event.payload

    if et == "asyncio.task.failed":
        exc = _str(p.get("exception_type")) or "unknown"
        msg = _str(p.get("exception_message"))
        return "warning", "critical", f"Task failed ({exc})", msg

    if et == "asyncio.task.cancelled":
        return "warning", "warning", "Task cancelled", _str(p.get("cancel_reason"))

    if et == "asyncio.gather.failed":
        exc = _str(p.get("exception_type")) or "unknown"
        return "warning", "critical", f"Gather failed ({exc})", None

    if et == "asyncio.gather.cancelled":
        return "warning", "warning", "Gather cancelled", None

    if et == "asyncio.queue.saturation.detected":
        qid = _str(p.get("queue_id")) or "?"
        return "saturation", "critical", f"Queue saturated: {qid}", None

    if et == "asyncio.queue.contention.detected":
        qid = _str(p.get("queue_id")) or "?"
        return "blocking", "warning", f"Queue contended: {qid}", None

    if et == "asyncio.queue.pressure.changed":
        new_level = _str(p.get("new_level"))
        if new_level in {"warning", "critical"}:
            sev: MarkerSeverity = "critical" if new_level == "critical" else "warning"
            qid = _str(p.get("queue_id")) or "?"
            return "saturation", sev, f"Queue pressure {new_level}: {qid}", None
        return None

    if et == "asyncio.semaphore.contention.detected":
        sid = _str(p.get("semaphore_id")) or "?"
        return "blocking", "warning", f"Semaphore contended: {sid}", None

    if et == "asyncio.executor.saturation.changed":
        new_level = _str(p.get("new_level"))
        if new_level in {"warning", "critical"}:
            sev = "critical" if new_level == "critical" else "warning"
            eid = _str(p.get("executor_id")) or "?"
            return "saturation", sev, f"Executor saturated: {eid}", None
        return None

    if et == "asyncio.executor.contention.detected":
        eid = _str(p.get("executor_id")) or "?"
        return "blocking", "warning", f"Executor contended: {eid}", None

    if et == "asyncio.executor.latency.spike.detected":
        eid = _str(p.get("executor_id")) or "?"
        return "blocking", "warning", f"Executor latency spike: {eid}", None

    if et == "asyncio.loop.blocked":
        ms = _str(p.get("duration_ms")) or _str(p.get("blocked_ms"))
        label = "Event loop blocked"
        if ms is not None:
            label = f"Event loop blocked ({ms} ms)"
        return "blocking", "critical", label, None

    return None


def _str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


# ── public API ────────────────────────────────────────────────────────


def derive_markers_and_bookmarks(
    frames: Iterable[dict[str, Any]],
    *,
    max_markers: int = 500,
    snapshot_buckets: int = 20,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Walk every frame once; emit markers + bookmarks.

    Args:
        frames: iterable of recorder-shape event dicts.
        max_markers: cap on total real-event markers (synthesized
            snapshot ticks don't count against it). When the cap is
            exceeded we keep the *first* N — operators care about
            "what went wrong first" more than later repeats of the
            same condition.
        snapshot_buckets: how many synthetic ``checkpoint`` markers to
            distribute evenly across the recording. These exist so the
            scrubber has visible anchor points even on recordings that
            captured no real saturation / failure events.
    """
    real_markers: list[dict[str, Any]] = []
    first_sequence: int | None = None
    first_monotonic_ns: int | None = None
    last_sequence: int | None = None
    last_monotonic_ns: int | None = None
    first_warning: _RawEvent | None = None
    first_blocking: _RawEvent | None = None
    first_saturation: _RawEvent | None = None
    first_failure: _RawEvent | None = None

    total = 0
    for raw in _iter_coerced(frames):
        total += 1
        if first_sequence is None:
            first_sequence = raw.sequence
            first_monotonic_ns = raw.monotonic_ns
        last_sequence = raw.sequence
        last_monotonic_ns = raw.monotonic_ns

        classification = _classify(raw)
        if classification is None:
            continue
        kind, severity, label, description = classification

        # Track the first occurrence of each landmark category — these
        # turn into auto-bookmarks below.
        if first_warning is None and severity in {"warning", "critical"}:
            first_warning = raw
        if first_blocking is None and kind == "blocking":
            first_blocking = raw
        if first_saturation is None and kind == "saturation":
            first_saturation = raw
        if first_failure is None and severity == "critical" and "failed" in raw.event_type:
            first_failure = raw

        if len(real_markers) >= max_markers:
            continue

        marker: dict[str, Any] = {
            "id": f"m-{raw.sequence}-{kind}",
            "kind": kind,
            "severity": severity,
            "sequence": raw.sequence,
            "monotonic_ns": raw.monotonic_ns,
            "label": label,
        }
        if description is not None and description != "":
            marker["description"] = description
        real_markers.append(marker)

    # Synthesized snapshot ticks — distributed across the recording so
    # the timeline has visual anchor points even when no real markers
    # exist. Skipped for tiny / empty recordings.
    snapshot_markers: list[dict[str, Any]] = []
    if (
        first_sequence is not None
        and last_sequence is not None
        and last_sequence > first_sequence
        and snapshot_buckets > 0
    ):
        span = last_sequence - first_sequence
        time_span = (
            (last_monotonic_ns or 0) - (first_monotonic_ns or 0)
            if first_monotonic_ns is not None and last_monotonic_ns is not None
            else 0
        )
        step = max(1, span // snapshot_buckets)
        for idx in range(snapshot_buckets):
            target = first_sequence + step * idx
            if target > last_sequence:
                break
            ratio = (target - first_sequence) / span if span > 0 else 0
            mono = (first_monotonic_ns or 0) + int(time_span * ratio)
            snapshot_markers.append(
                {
                    "id": f"snap-{idx}",
                    "kind": "checkpoint",
                    "severity": "info",
                    "sequence": target,
                    "monotonic_ns": mono,
                    "label": f"Snapshot {idx + 1} / {snapshot_buckets}",
                },
            )

    markers = real_markers + snapshot_markers

    # ── auto bookmarks ────────────────────────────────────────────────
    bookmarks: list[dict[str, Any]] = []
    created_ms = 0  # static — bookmarks generated at load time, not user-created

    if first_sequence is not None and first_monotonic_ns is not None:
        bookmarks.append(
            {
                "id": "bm-runtime-started",
                "label": "Runtime started",
                "sequence": first_sequence,
                "monotonic_ns": first_monotonic_ns,
                "created_at_ms": created_ms,
            },
        )

    if first_warning is not None:
        bookmarks.append(
            {
                "id": "bm-first-warning",
                "label": "First warning",
                "sequence": first_warning.sequence,
                "monotonic_ns": first_warning.monotonic_ns,
                "created_at_ms": created_ms,
                "note": _classification_label(first_warning),
            },
        )

    if first_saturation is not None:
        bookmarks.append(
            {
                "id": "bm-first-saturation",
                "label": "First saturation",
                "sequence": first_saturation.sequence,
                "monotonic_ns": first_saturation.monotonic_ns,
                "created_at_ms": created_ms,
                "note": _classification_label(first_saturation),
            },
        )

    if first_blocking is not None:
        bookmarks.append(
            {
                "id": "bm-first-blocking",
                "label": "Blocking detected",
                "sequence": first_blocking.sequence,
                "monotonic_ns": first_blocking.monotonic_ns,
                "created_at_ms": created_ms,
                "note": _classification_label(first_blocking),
            },
        )

    if first_failure is not None:
        bookmarks.append(
            {
                "id": "bm-first-failure",
                "label": "First failure",
                "sequence": first_failure.sequence,
                "monotonic_ns": first_failure.monotonic_ns,
                "created_at_ms": created_ms,
                "note": _classification_label(first_failure),
            },
        )

    if (
        last_sequence is not None
        and last_monotonic_ns is not None
        and (first_sequence is None or last_sequence > first_sequence)
    ):
        bookmarks.append(
            {
                "id": "bm-runtime-stopped",
                "label": "Runtime stopped",
                "sequence": last_sequence,
                "monotonic_ns": last_monotonic_ns,
                "created_at_ms": created_ms,
            },
        )

    return markers, bookmarks


def _iter_coerced(frames: Iterable[dict[str, Any]]) -> Iterator[_RawEvent]:
    for raw in frames:
        event = _coerce(raw)
        if event is not None:
            yield event


def _classification_label(event: _RawEvent) -> str | None:
    classification = _classify(event)
    return classification[2] if classification else None
