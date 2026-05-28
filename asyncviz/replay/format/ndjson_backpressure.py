"""Backpressure + safety limits for the replay format codec.

The encoder/decoder are pure functions, but the *writer* and *reader*
that sit on top of them can be misused — a runaway producer can
exhaust memory by spitting out frames faster than the disk can
absorb, and a malicious recording can exhaust memory by handing the
decoder a multi-gigabyte single line.

This module exposes the small set of safety caps both paths use:

* :data:`MAX_FRAME_LINE_BYTES` — the longest line the decoder will
  attempt. Beyond this we drop the frame as malformed rather than
  let it OOM us.
* :data:`MAX_ENCODER_BUFFER_FRAMES` — soft cap for the asynchronous
  encoder's pending-frame buffer.
* :class:`OverflowGuard` — small counter used by the writer to
  detect sustained overload (so a one-off spike doesn't trip an
  alarm but a true overflow does).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Final

from asyncviz.replay.format.ndjson_observability import get_format_metrics
from asyncviz.replay.format.ndjson_tracing import record_ndjson_trace

MAX_FRAME_LINE_BYTES: Final[int] = 8 * 1024 * 1024  # 8 MiB
"""Hard cap on the decoded length of a single NDJSON line. Anything
larger is rejected before parsing so a corrupted file can't OOM the
reader. 8 MiB is well above any reasonable runtime event payload."""

MAX_ENCODER_BUFFER_FRAMES: Final[int] = 65536
"""Soft cap on the asynchronous encoder's pending-frame backlog.
Hitting this trips a backpressure event; the writer falls back to a
synchronous flush."""

DEFAULT_OVERFLOW_WINDOW_SECONDS: Final[float] = 1.0
"""Time window within which repeated overflow events are aggregated
before being treated as 'sustained overload'."""


class FrameTooLargeError(ValueError):
    """Raised when a frame would exceed :data:`MAX_FRAME_LINE_BYTES`."""


def guard_line_length(line: str | bytes) -> None:
    """Reject lines beyond the safety cap. The decoder calls this
    before any JSON parsing happens."""
    size = len(line) if isinstance(line, bytes) else len(line.encode("utf-8"))
    if size > MAX_FRAME_LINE_BYTES:
        get_format_metrics().record_backpressure_event()
        record_ndjson_trace("backpressure", f"line_too_large bytes={size}")
        raise FrameTooLargeError(
            f"NDJSON line exceeds {MAX_FRAME_LINE_BYTES} bytes (got {size})",
        )


@dataclass(slots=True)
class OverflowGuard:
    """Tracks transient vs sustained overload."""

    window_seconds: float = DEFAULT_OVERFLOW_WINDOW_SECONDS
    threshold: int = 16
    _window_start: float = 0.0
    _count: int = 0
    _lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._lock is None:
            self._lock = threading.Lock()

    def trip(self) -> bool:
        """Record one overflow event. Returns True when the
        threshold is crossed within the active window (i.e. the
        caller should consider this 'sustained')."""
        now = time.monotonic()
        with self._lock:
            if now - self._window_start > self.window_seconds:
                self._window_start = now
                self._count = 0
            self._count += 1
            sustained = self._count >= self.threshold
        get_format_metrics().record_backpressure_event()
        record_ndjson_trace("backpressure", f"count={self._count} sustained={sustained}")
        return sustained

    def reset(self) -> None:
        with self._lock:
            self._window_start = 0.0
            self._count = 0
