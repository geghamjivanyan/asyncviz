"""Render-subsystem failure isolation adapter.

A render-pass failure must never tear down the whole canvas. The
adapter wraps each pass in a boundary; when a pass's breaker trips,
the manager can switch the render pipeline to a documented fallback
mode (data-only, keyframe-only, …) without rebooting.
"""

from __future__ import annotations

import threading
from typing import Literal

from asyncviz.runtime.resilience.failure_domain import FailureDomain
from asyncviz.runtime.resilience.subsystem_boundary import SubsystemBoundary

RenderFallbackMode = Literal["normal", "data-only", "keyframe-only", "blank"]


class RenderFailureIsolation:
    __slots__ = ("_disabled", "_domain", "_fallback_mode", "_lock")

    def __init__(self, domain: FailureDomain) -> None:
        self._domain = domain
        self._lock = threading.Lock()
        self._disabled: set[str] = set()
        self._fallback_mode: RenderFallbackMode = "normal"

    def isolate_pass(
        self,
        *,
        pass_id: str,
        suppress: bool = True,
    ) -> SubsystemBoundary:
        return SubsystemBoundary(
            self._domain,
            payload_kind=pass_id,
            suppress=suppress,
            on_failure=lambda event: self._note_disabled(event.payload_kind),
            swallow_unavailable=True,
        )

    def disabled_passes(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._disabled))

    def set_fallback_mode(self, mode: RenderFallbackMode) -> None:
        with self._lock:
            self._fallback_mode = mode

    def fallback_mode(self) -> RenderFallbackMode:
        with self._lock:
            return self._fallback_mode

    def reinstate(self, pass_id: str) -> bool:
        with self._lock:
            existed = pass_id in self._disabled
            self._disabled.discard(pass_id)
        if existed:
            self._domain.release_quarantine(pass_id)
        return existed

    def _note_disabled(self, pass_id: str) -> None:
        if not pass_id:
            return
        with self._lock:
            self._disabled.add(pass_id)
