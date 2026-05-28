"""Frame + sequence validation.

Two layers of validation live here:

1. **Single-frame validation** — checks one frame in isolation: did
   it parse, does it have the required envelope keys, is the
   ``frame_type`` recognized, is the payload sane.
2. **Stream validation** — checks an *ordered* sequence of frames:
   monotonic sequence numbers, no duplicates, no gaps (gap policy
   configurable).

The two are separate so callers can validate either side. The
streaming reader uses both; one-shot decoders typically use only the
single-frame layer.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_observability import get_format_metrics
from asyncviz.replay.format.ndjson_schema import (
    ALL_FRAME_TYPES,
    REQUIRED_ENVELOPE_KEYS,
    SCHEMA_VERSION,
)
from asyncviz.replay.format.ndjson_tracing import record_ndjson_trace


class FrameValidationError(ValueError):
    """Raised when a frame fails validation."""


@dataclass(frozen=True, slots=True)
class FrameValidationReport:
    """Result of validating one frame."""

    valid: bool
    issues: tuple[str, ...] = ()

    def raise_if_invalid(self) -> None:
        if not self.valid:
            raise FrameValidationError("; ".join(self.issues))


def validate_frame(frame: ReplayFrame) -> FrameValidationReport:
    """Validate one decoded frame's envelope. Payload validation is
    the codec's job (run via :func:`decode_payload`)."""
    issues: list[str] = []
    missing = REQUIRED_ENVELOPE_KEYS - {
        "schema_version",
        "frame_type",
        "sequence",
        "monotonic_ns",
        "payload_type",
        "payload",
    }
    # The required keys are always set on a constructed frame; we
    # still check the *values* for type sanity.
    if frame.schema_version < 1:
        issues.append(f"schema_version must be >= 1 (got {frame.schema_version})")
    if frame.schema_version > SCHEMA_VERSION:
        # Not fatal — already noted as a skew by the decoder. We let
        # it pass so the caller can decide whether to drop the frame.
        pass
    if frame.frame_type not in ALL_FRAME_TYPES:
        issues.append(f"unknown frame_type {frame.frame_type!r}")
    if not isinstance(frame.sequence, int) or frame.sequence < 0:
        issues.append(f"sequence must be a non-negative int (got {frame.sequence!r})")
    if not isinstance(frame.monotonic_ns, int) or frame.monotonic_ns < 0:
        issues.append(f"monotonic_ns must be a non-negative int (got {frame.monotonic_ns!r})")
    if not frame.payload_type:
        issues.append("payload_type is empty")
    if not isinstance(frame.payload, dict):
        issues.append(f"payload must be a dict (got {type(frame.payload).__name__})")
    if missing:  # pragma: no cover — kept for completeness
        issues.append(f"missing required keys: {sorted(missing)}")
    if issues:
        get_format_metrics().record_validation_failure()
        record_ndjson_trace(
            "validation-failed",
            f"seq={frame.sequence} type={frame.frame_type} issues={len(issues)}",
        )
    return FrameValidationReport(valid=not issues, issues=tuple(issues))


# ── stream-level validation ───────────────────────────────────────


@dataclass(slots=True)
class SequenceValidator:
    """Stateful validator across a stream of frames.

    Use it by feeding every decoded frame through :meth:`observe`.
    The validator records sequence violations and duplicates against
    the metrics singleton; the per-frame return value tells the
    caller whether *this* frame was clean."""

    allow_gaps: bool = False
    """When False (default), any gap in the sequence numbers is a
    violation. Recordings *can* legitimately have gaps when the
    producer's bounded buffer dropped frames; readers that expect
    that should opt into ``allow_gaps=True``."""

    _last_sequence: int = -1
    _seen: set[int] = field(default_factory=set)

    def reset(self) -> None:
        self._last_sequence = -1
        self._seen.clear()

    def observe(self, frame: ReplayFrame) -> tuple[bool, str]:
        """Returns ``(clean, reason)``. ``clean=True`` means the
        sequence number satisfied the configured policy."""
        seq = frame.sequence
        if seq in self._seen:
            get_format_metrics().record_duplicate_sequence()
            record_ndjson_trace("validation-failed", f"dup seq={seq}")
            return False, f"duplicate sequence {seq}"
        self._seen.add(seq)
        if self._last_sequence < 0:
            self._last_sequence = seq
            return True, ""
        if seq <= self._last_sequence:
            get_format_metrics().record_sequence_violation()
            record_ndjson_trace(
                "validation-failed",
                f"out-of-order seq={seq} after {self._last_sequence}",
            )
            return False, f"sequence {seq} not strictly after {self._last_sequence}"
        gap = seq - self._last_sequence - 1
        self._last_sequence = seq
        if gap > 0 and not self.allow_gaps:
            get_format_metrics().record_sequence_violation()
            record_ndjson_trace(
                "validation-failed",
                f"gap seq={seq} gap={gap}",
            )
            return False, f"unexpected gap of {gap} before sequence {seq}"
        return True, ""


def validate_stream(
    frames: Iterable[ReplayFrame], *, allow_gaps: bool = False,
) -> Iterator[tuple[ReplayFrame, bool, str]]:
    """Yield ``(frame, clean, reason)`` triples. Both the frame and
    the verdict so callers can decide whether to keep or drop."""
    validator = SequenceValidator(allow_gaps=allow_gaps)
    for frame in frames:
        per_frame = validate_frame(frame)
        if not per_frame.valid:
            yield frame, False, "; ".join(per_frame.issues)
            continue
        clean, reason = validator.observe(frame)
        yield frame, clean, reason
