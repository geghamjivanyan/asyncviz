"""Replay loader configuration.

One immutable dataclass that controls every knob of the loader. Keep
construction cheap so tests can build many configs without paying
for option-parsing churn.

Defaults are picked for the common case: open a local recording,
iterate through it lazily, isolate any corruption automatically. The
opt-in flags (``verify_integrity``, ``strict_mode``) trade tolerance
for confidence — useful for replay-archive ingestion pipelines that
want loud failures rather than silent skips.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FrameFormat = Literal["auto", "canonical", "legacy_recording"]
"""How the loader interprets each NDJSON line.

* ``auto`` (default) — peek at the first line, then commit to one
  interpretation for the rest of the session.
* ``canonical`` — every line must decode via the format layer's
  :func:`decode_frame`.
* ``legacy_recording`` — lines follow the recorder's pre-9.2 frame
  format (``sequence`` / ``event_id`` / ``event_type`` /
  ``monotonic_ns`` / ``payload``).
"""


@dataclass(frozen=True, slots=True)
class ReplayLoaderConfig:
    """Immutable replay-loader configuration."""

    session_dir: Path
    """Path to a recording session directory (containing
    ``manifest.json`` + ``events/`` + optional ``snapshots/``)."""

    frame_format: FrameFormat = "auto"
    """How to interpret the bytes inside event chunks."""

    strict_mode: bool = False
    """If True, malformed lines and validation failures raise instead
    of being skipped + counted. Use for replay-archive ingestion."""

    verify_integrity: bool = False
    """If True, every opened chunk has its SHA-256 verified against
    the manifest before the loader yields any of its frames. Slow on
    large recordings — opt-in only."""

    allow_sequence_gaps: bool = True
    """If True (default), gaps in the sequence numbers are tolerated.
    Recordings *do* legitimately drop frames under load (drop-newest
    backpressure), so this default avoids spurious failures."""

    max_buffer_frames: int = 4096
    """Soft cap on the loader's pending decoded-frame buffer when an
    upstream consumer applies backpressure. The loader is pull-based
    so this is rarely hit; it exists for the rare case where a
    bounded internal queue gets layered on top."""

    snapshot_dirname: str = "snapshots"
    """Override only if a recording layout uses a non-standard
    snapshot directory name."""

    events_dirname: str = "events"
    """Override only if a recording layout uses a non-standard
    events directory name."""

    def chunk_dir(self) -> Path:
        return self.session_dir / self.events_dirname

    def snapshot_dir(self) -> Path:
        return self.session_dir / self.snapshot_dirname
