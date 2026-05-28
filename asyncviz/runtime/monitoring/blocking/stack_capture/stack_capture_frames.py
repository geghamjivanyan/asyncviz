"""Canonical captured-frame value types.

A *captured stack* is an ordered sequence of *captured frames* plus
provenance metadata. Both are frozen dataclasses with stable
serialization — same inputs yield byte-identical JSON.

Production code constructs these via :class:`LiveFrameProvider`; tests
build them directly through :func:`build_synthetic_frame`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    """One frame from a captured stack.

    Field shape matches what the dashboard needs to render a clickable
    source location:

    * ``filename``       — absolute path; the wire layer never trims
      this so consumers can decide what to display.
    * ``module``         — best-effort module dotted path; may be empty
      when the frame is from an exec'd / lambda context.
    * ``function``       — code object's ``co_name``.
    * ``lineno``         — 1-based source line.
    * ``code_context``   — optional one-line code excerpt, populated
      when the configured source resolver can read the file.
    * ``is_async``       — true when ``co_flags`` indicates a coroutine
      / async generator code object. Lets the UI render an "await"
      glyph without re-parsing.
    * ``is_internal``    — true when the frame's module matches the
      configured internal-prefix list (asyncio / asyncviz). The filter
      stage usually drops these; we preserve the flag so consumers can
      opt-in to seeing them.

    Frozen + slotted — these flow through hot paths and we want zero
    per-frame allocation overhead beyond the dataclass itself.
    """

    filename: str
    module: str
    function: str
    lineno: int
    code_context: str | None
    is_async: bool
    is_internal: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "module": self.module,
            "function": self.function,
            "lineno": self.lineno,
            "code_context": self.code_context,
            "is_async": self.is_async,
            "is_internal": self.is_internal,
        }


@dataclass(frozen=True, slots=True)
class CapturedTaskMetadata:
    """Best-effort task context for the captured frame.

    Empty when the engine can't (or wasn't asked to) correlate with the
    asyncio task registry. Present even on synthetic captures so the
    payload shape stays uniform.
    """

    task_id: str | None = None
    task_name: str | None = None
    coroutine_name: str | None = None
    parent_task_id: str | None = None
    root_task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "coroutine_name": self.coroutine_name,
            "parent_task_id": self.parent_task_id,
            "root_task_id": self.root_task_id,
        }


@dataclass(frozen=True, slots=True)
class CapturedStack:
    """One captured stack snapshot. The unit of work the engine emits.

    Identity fields:

    * ``capture_id``     — monotonically-allocated per engine; replays
      receive the same sequence so consumers can dedup.
    * ``runtime_id``     — issuing clock identity.
    * ``monotonic_ns``   — capture instant; used by downstream tools
      to correlate with the freeze window's timeline.
    * ``sample_index``   — lag-monitor sample that triggered the
      capture; ``None`` when the engine captured outside a sample
      (e.g. manual capture).
    * ``window_id``      — id of the freeze window the capture belongs
      to, when correlated; ``None`` otherwise.
    * ``severity``       — string name of the effective blocking
      severity at capture time. Kept as a string so the value type
      doesn't import the enum.
    * ``trigger``        — short string describing what fired the
      capture (``"violation"``, ``"escalation"``, ``"freeze"``,
      ``"manual"``, etc.).

    Payload fields:

    * ``frames``         — ordered tuple, top-of-stack first (innermost
      function the runtime was executing at capture time).
    * ``frames_total``   — raw count before depth-truncation. Lets the
      UI flag "stack truncated".
    * ``filtered_count`` — frames the filter stage dropped from the
      raw walk. Together with ``frames`` lets you reconstruct the
      raw-vs-displayed split.
    * ``thread_id``      — id of the thread the walk targeted. Today
      always the main loop thread; reserved for multi-thread captures.
    * ``task``           — :class:`CapturedTaskMetadata`, possibly empty.
    """

    capture_id: int
    runtime_id: str
    monotonic_ns: int
    sample_index: int | None
    window_id: str | None
    severity: str
    trigger: str
    frames: tuple[CapturedFrame, ...]
    frames_total: int
    filtered_count: int
    thread_id: int
    task: CapturedTaskMetadata = field(default_factory=CapturedTaskMetadata)

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def truncated(self) -> bool:
        return self.frames_total > len(self.frames) + self.filtered_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "runtime_id": self.runtime_id,
            "monotonic_ns": self.monotonic_ns,
            "sample_index": self.sample_index,
            "window_id": self.window_id,
            "severity": self.severity,
            "trigger": self.trigger,
            "frames": [f.to_dict() for f in self.frames],
            "frame_count": self.frame_count,
            "frames_total": self.frames_total,
            "filtered_count": self.filtered_count,
            "truncated": self.truncated,
            "thread_id": self.thread_id,
            "task": self.task.to_dict(),
        }
