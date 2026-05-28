"""Structured pause / resume / step requests.

The coordinator accepts these as opaque value objects so a future
remote-control path (collaborative replay, debugger integration) can
ship them over the wire without restructuring the API.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from asyncviz.replay.runtime.control.replay_playback_configuration import (
    PauseTrigger,
)


@dataclass(frozen=True, slots=True)
class PauseRequest:
    """One pause intent."""

    request_id: int
    """Monotonic id assigned by the coordinator on acceptance."""

    trigger: PauseTrigger = "after_current_frame"

    target_sequence: int = 0
    """Required when ``trigger == "at_sequence"``."""

    target_monotonic_ns: int = 0
    """Required when ``trigger == "at_timestamp"``."""

    reason: str = ""
    """Free-form annotation (UI label, breakpoint id, debugger note)."""

    requested_at_ns: int = field(default_factory=time.monotonic_ns)


@dataclass(frozen=True, slots=True)
class ResumeRequest:
    """One resume intent."""

    request_id: int
    """Monotonic id assigned by the coordinator on acceptance."""

    reason: str = ""

    requested_at_ns: int = field(default_factory=time.monotonic_ns)


@dataclass(frozen=True, slots=True)
class StepRequest:
    """Step-forward intent — dispatches a single frame, then leaves
    the engine paused."""

    request_id: int

    frame_count: int = 1
    """Number of frames to dispatch before re-pausing. Defaults to 1
    — the canonical single-frame step."""

    reason: str = ""

    requested_at_ns: int = field(default_factory=time.monotonic_ns)
