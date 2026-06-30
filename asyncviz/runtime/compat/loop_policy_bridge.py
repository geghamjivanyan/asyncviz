"""Event-loop policy bridge.

Installs uvloop's event-loop policy *atomically* — if anything goes
wrong, the previously-active policy is restored before the helper
returns. The bridge never installs a policy when a loop is already
running (asyncio forbids that anyway) and never silently swallows a
policy change the operator made themselves.

The bridge is *idempotent*: calling :meth:`install_uvloop_policy`
twice is a no-op the second time. :meth:`restore_default_policy`
restores the policy captured at construction time, not the previous
call's policy.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from asyncviz.runtime.compat.loop_feature_detection import (
    is_running_under_uvloop,
    is_uvloop_available,
)

if TYPE_CHECKING:
    from asyncio.events import AbstractEventLoopPolicy


class UvloopUnavailableError(RuntimeError):
    """Raised by :meth:`install_uvloop_policy` when uvloop is not
    importable + ``fallback`` is ``False``."""


class LoopPolicyBridge:
    """Idempotent uvloop policy installer."""

    __slots__ = ("_baseline_policy", "_installed")

    def __init__(self) -> None:
        self._baseline_policy: AbstractEventLoopPolicy | None = self._safe_current_policy()
        self._installed = False

    @property
    def installed(self) -> bool:
        return self._installed

    def install_uvloop_policy(self, *, fallback: bool = True) -> bool:
        """Install the uvloop policy. Returns ``True`` if installed.

        * Idempotent: a no-op when already installed.
        * Never installs while a loop is running — that's a runtime
          error in asyncio anyway.
        * Restores the baseline policy on any failure when
          ``fallback=True``; raises :class:`UvloopUnavailableError`
          otherwise.
        """
        if self._installed:
            return True
        if self._loop_is_running():
            if fallback:
                return False
            raise UvloopUnavailableError(
                "cannot swap event-loop policy while a loop is running",
            )
        if not is_uvloop_available():
            if fallback:
                return False
            raise UvloopUnavailableError("uvloop is not importable")
        try:
            import uvloop

            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            self._installed = True
            return True
        except Exception as exc:
            self._restore_baseline()
            if fallback:
                return False
            raise UvloopUnavailableError(f"uvloop install failed: {exc}") from exc

    def restore_default_policy(self) -> bool:
        """Restore the policy captured at construction. Returns
        ``True`` when the policy actually changed."""
        if not self._installed:
            return False
        changed = self._restore_baseline()
        if changed:
            self._installed = False
        return changed

    # ── internals ────────────────────────────────────────────────

    def _restore_baseline(self) -> bool:
        if self._baseline_policy is None:
            return False
        try:
            current = self._safe_current_policy()
        except Exception:
            current = None
        if current is self._baseline_policy:
            return False
        with contextlib.suppress(Exception):
            asyncio.set_event_loop_policy(self._baseline_policy)
            return True
        return False

    @staticmethod
    def _safe_current_policy() -> AbstractEventLoopPolicy | None:
        try:
            return asyncio.get_event_loop_policy()
        except Exception:
            return None

    @staticmethod
    def _loop_is_running() -> bool:
        return not is_running_under_uvloop(None) and _has_running_loop()


def _has_running_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True
