"""Synthetic frame helpers — used by tests + replay tools.

Provides cheap constructors for :class:`RawFrame` + a static provider
so tests don't need to manipulate real Python frames to drive the
sampler.
"""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_sampler import (
    RawFrame,
    StaticFrameProvider,
)


def build_raw_frame(
    *,
    filename: str = "/tmp/synthetic.py",
    module: str = "myapp.code",
    function: str = "do_work",
    lineno: int = 1,
    co_flags: int = 0,
) -> RawFrame:
    """One-line builder for a synthetic :class:`RawFrame`."""
    return RawFrame(
        filename=filename,
        module=module,
        function=function,
        lineno=lineno,
        co_flags=co_flags,
    )


def build_static_provider(frames: Iterable[RawFrame]) -> StaticFrameProvider:
    """Wrap an iterable of raw frames in a :class:`StaticFrameProvider`."""
    return StaticFrameProvider(frames)
