"""Stack → JSON serialization with deterministic payload-size bounds.

Two concerns:

* **Determinism**: identical :class:`CapturedStack` inputs serialize to
  byte-identical JSON. The dataclass field order is fixed; the
  serializer never reads the clock.
* **Bounded payload**: a deep stack with long code-context lines can
  produce a huge JSON blob. The serializer measures the rendered
  payload and trims frames from the *bottom* (oldest call) until it
  fits, preserving top-of-stack which is where root causes live.

The serializer doesn't emit events directly — it produces the dict the
engine wraps in a :class:`GenericEvent`. Keeps the event layer free of
trimming logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedFrame,
    CapturedStack,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_limits import (
    StackCaptureLimits,
)


@dataclass(frozen=True, slots=True)
class SerializationOutcome:
    """Result of one serialize call.

    * ``payload`` — the JSON-safe dict.
    * ``json_bytes`` — pre-rendered JSON byte count. Lets metrics +
      backpressure measure without re-rendering.
    * ``trimmed`` — true when the serializer dropped frames to fit
      ``max_payload_bytes``. ``original_frame_count`` carries the
      pre-trim count so the UI can flag truncation.
    """

    payload: dict[str, object]
    json_bytes: int
    trimmed: bool
    original_frame_count: int


class StackSerializer:
    """Stateless JSON serializer with bounded payload."""

    __slots__ = ("_limits",)

    def __init__(self, *, limits: StackCaptureLimits) -> None:
        self._limits = limits

    @property
    def limits(self) -> StackCaptureLimits:
        return self._limits

    def serialize(self, stack: CapturedStack) -> SerializationOutcome:
        # Render once to measure. If too large, drop bottom frames in a
        # bounded loop until it fits or we hit the empty-frame floor.
        payload = stack.to_dict()
        rendered = self._encode(payload)
        if len(rendered) <= self._limits.max_payload_bytes:
            return SerializationOutcome(
                payload=payload,
                json_bytes=len(rendered),
                trimmed=False,
                original_frame_count=stack.frame_count,
            )

        original_frame_count = stack.frame_count
        frames = list(stack.frames)
        trimmed = False
        while frames and len(rendered) > self._limits.max_payload_bytes:
            frames.pop()  # drop oldest (deepest call → bottom of trace)
            trimmed = True
            payload = self._rewrite_frames(stack, frames)
            rendered = self._encode(payload)
        return SerializationOutcome(
            payload=payload,
            json_bytes=len(rendered),
            trimmed=trimmed,
            original_frame_count=original_frame_count,
        )

    @staticmethod
    def _encode(payload: dict[str, object]) -> bytes:
        # ``separators`` removes whitespace; ``sort_keys=False`` because
        # the dataclass ``to_dict`` already imposes a stable field order
        # — sorting alphabetically would scramble it.
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _rewrite_frames(stack: CapturedStack, frames: list[CapturedFrame]) -> dict[str, object]:
        # Re-render the payload with the trimmed frame list.
        payload = stack.to_dict()
        payload["frames"] = [f.to_dict() for f in frames]
        payload["frame_count"] = len(frames)
        payload["truncated"] = True
        return payload
