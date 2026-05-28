"""Capture limit policy.

Frame walks need bounded depth so:

* a pathologically deep stack can't blow up the serialization payload.
* per-capture cost is bounded — the walk + the filter + the source
  resolution all scale with depth.

Limits are deliberately a separate value type (not just two fields on
:class:`StackCaptureConfiguration`) so the policy module can pass them
to the sampler / serializer independently of the larger config blob.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Bounded by Python's own recursion limit (~1000 by default) — a
#: deeper-than-this stack is almost certainly pathology and capturing
#: all of it would mostly produce noise.
DEFAULT_MAX_DEPTH: int = 64

#: Source-line snippet character cap. The serializer truncates each
#: captured ``code_context`` to this length to keep payloads small.
DEFAULT_MAX_CODE_LENGTH: int = 200

#: Hard ceiling on the JSON payload size (bytes, post-serialization).
#: The serializer trims frames from the bottom until this budget fits
#: — top-of-stack stays intact because that's where root causes live.
DEFAULT_MAX_PAYLOAD_BYTES: int = 16 * 1024


@dataclass(frozen=True, slots=True)
class StackCaptureLimits:
    max_depth: int = DEFAULT_MAX_DEPTH
    max_code_length: int = DEFAULT_MAX_CODE_LENGTH
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES
    capture_code_context: bool = True

    def __post_init__(self) -> None:
        if self.max_depth <= 0:
            raise ValueError(f"max_depth must be > 0 (got {self.max_depth})")
        if self.max_code_length <= 0:
            raise ValueError(f"max_code_length must be > 0 (got {self.max_code_length})")
        if self.max_payload_bytes <= 0:
            raise ValueError(f"max_payload_bytes must be > 0 (got {self.max_payload_bytes})")

    def to_dict(self) -> dict[str, object]:
        return {
            "max_depth": self.max_depth,
            "max_code_length": self.max_code_length,
            "max_payload_bytes": self.max_payload_bytes,
            "capture_code_context": self.capture_code_context,
        }
