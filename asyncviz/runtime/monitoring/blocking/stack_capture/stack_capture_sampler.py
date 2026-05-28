"""Frame walker — turn live runtime frames into :class:`CapturedFrame` objects.

Two providers:

* :class:`LiveFrameProvider` — production. Walks ``sys._getframe()``
  (or the frame supplied by the engine, which lets the engine target a
  specific thread).
* :class:`StaticFrameProvider` — tests. Returns a pre-built list.

Both honor the configured :class:`StackCaptureLimits` and
:class:`FilterPolicy`. The sampler never reads the wall clock; the
engine stamps timestamps separately so the sampler stays deterministic
on its inputs.
"""

from __future__ import annotations

import linecache
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from types import CodeType, FrameType
from typing import Protocol, runtime_checkable

from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_filters import (
    FilterPolicy,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedFrame,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_limits import (
    StackCaptureLimits,
)

# CPython's coroutine / async-generator flags. Matches
# inspect.CO_COROUTINE / CO_ASYNC_GENERATOR; we hard-code them so tests
# without ``inspect`` available stay portable.
_CO_COROUTINE = 0x100
_CO_ASYNC_GENERATOR = 0x200
_CO_ITERABLE_COROUTINE = 0x400


@dataclass(frozen=True, slots=True)
class RawFrame:
    """Provider-agnostic intermediate frame record.

    Separates "where does the frame come from" from "what we serialize".
    Lets the static provider populate the fields without touching the
    Python frame machinery at all.
    """

    filename: str
    module: str
    function: str
    lineno: int
    co_flags: int


@runtime_checkable
class FrameProvider(Protocol):
    """Source of raw frames for the sampler."""

    def collect(self) -> Sequence[RawFrame]:  # pragma: no cover - protocol
        ...


class LiveFrameProvider:
    """Walk the current Python frame stack.

    By default reads :func:`sys._getframe` to find the calling context;
    pass a ``frame_factory`` callable to target a specific thread's
    frame (``sys._current_frames()[thread_id]``).
    """

    __slots__ = ("_frame_factory", "_skip_engine_frames")

    def __init__(
        self,
        *,
        frame_factory=None,
        skip_engine_frames: int = 0,
    ) -> None:
        self._frame_factory = frame_factory
        self._skip_engine_frames = max(0, skip_engine_frames)

    def collect(self) -> Sequence[RawFrame]:
        frame: FrameType | None = (
            self._frame_factory() if self._frame_factory is not None else sys._getframe(1)
        )
        # Skip the engine's own frames so the captured stack starts at
        # user code. The engine passes the number of synthetic frames
        # between the user code and ``collect()``.
        skipped = 0
        while frame is not None and skipped < self._skip_engine_frames:
            frame = frame.f_back
            skipped += 1
        out: list[RawFrame] = []
        # ``f_back`` walks toward the caller — i.e. away from the
        # current execution point. We collect inner-first so consumers
        # get top-of-stack at index 0 (matches traceback semantics).
        while frame is not None:
            code: CodeType = frame.f_code
            module = _module_for_frame(frame)
            out.append(
                RawFrame(
                    filename=code.co_filename,
                    module=module,
                    function=code.co_name,
                    lineno=frame.f_lineno,
                    co_flags=code.co_flags,
                )
            )
            frame = frame.f_back
        return out


class StaticFrameProvider:
    """Test provider — returns the frames it was constructed with."""

    __slots__ = ("_frames",)

    def __init__(self, frames: Iterable[RawFrame]) -> None:
        self._frames = tuple(frames)

    def collect(self) -> Sequence[RawFrame]:
        return self._frames


def _module_for_frame(frame: FrameType) -> str:
    """Best-effort module path for ``frame``.

    Falls back to the filename's stem when no ``__name__`` is bound in
    the frame's globals (e.g. an exec'd snippet).
    """
    globals_ = frame.f_globals
    name = globals_.get("__name__")
    if isinstance(name, str) and name:
        return name
    return ""


def _is_async_code(co_flags: int) -> bool:
    return bool(co_flags & (_CO_COROUTINE | _CO_ASYNC_GENERATOR | _CO_ITERABLE_COROUTINE))


@dataclass(frozen=True, slots=True)
class SampleOutcome:
    """Result of one sampler invocation.

    ``frames`` carries the post-filter list ready to embed in
    :class:`CapturedStack`. ``frames_total`` is the raw walk depth
    (pre-truncation); ``filtered_count`` is what the filter chain
    dropped. Together they tell the engine + UI how much of the picture
    they're showing.
    """

    frames: tuple[CapturedFrame, ...]
    frames_total: int
    filtered_count: int


class StackSampler:
    """Pure conversion layer from :class:`RawFrame` → :class:`CapturedFrame`.

    Stateless; instances are cheap and reusable. Honors the configured
    :class:`StackCaptureLimits` for depth + code-context truncation and
    the :class:`FilterPolicy` for internal-frame handling.
    """

    __slots__ = ("_filters", "_limits")

    def __init__(
        self,
        *,
        limits: StackCaptureLimits,
        filters: FilterPolicy,
    ) -> None:
        self._limits = limits
        self._filters = filters

    @property
    def limits(self) -> StackCaptureLimits:
        return self._limits

    @property
    def filters(self) -> FilterPolicy:
        return self._filters

    def sample(self, provider: FrameProvider) -> SampleOutcome:
        raw = list(provider.collect())
        # Bound depth before doing any per-frame work so a runaway
        # stack can't burn cycles on filter / source lookups we'll
        # immediately discard.
        frames_total = len(raw)
        if frames_total > self._limits.max_depth:
            raw = raw[: self._limits.max_depth]
        filtered = 0
        out: list[CapturedFrame] = []
        for r in raw:
            internal = self._filters.is_internal(r.module, r.filename)
            if internal and not self._filters.include_internal_frames:
                filtered += 1
                continue
            code_context = self._resolve_code_context(r)
            out.append(
                CapturedFrame(
                    filename=r.filename,
                    module=r.module,
                    function=r.function,
                    lineno=r.lineno,
                    code_context=code_context,
                    is_async=_is_async_code(r.co_flags),
                    is_internal=internal,
                )
            )
        return SampleOutcome(
            frames=tuple(out),
            frames_total=frames_total,
            filtered_count=filtered,
        )

    def _resolve_code_context(self, raw: RawFrame) -> str | None:
        if not self._limits.capture_code_context:
            return None
        try:
            line = linecache.getline(raw.filename, raw.lineno)
        except (OSError, ValueError):
            return None
        if not line:
            return None
        line = line.rstrip("\n").strip()
        if len(line) > self._limits.max_code_length:
            line = line[: self._limits.max_code_length - 1] + "…"
        return line
