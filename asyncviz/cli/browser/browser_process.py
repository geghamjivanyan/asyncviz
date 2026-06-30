"""Cross-platform wrapper around ``webbrowser.open``.

Isolated so:

* Tests can swap the actual platform call with a fake without
  monkey-patching :mod:`webbrowser`.
* Future platform-specific paths (e.g. PyInstaller, WSL ``cmd.exe
  /c start``, headless browsers for screenshots) plug in here.
"""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ProcessLaunchOutcome:
    """Outcome of one platform-level open attempt."""

    success: bool
    detail: str
    backend: Literal["webbrowser", "stub", "noop"] = "webbrowser"


class BrowserBackend(Protocol):
    """Pluggable browser-launch backend."""

    def open(self, url: str) -> ProcessLaunchOutcome:  # pragma: no cover — Protocol
        ...


class WebbrowserBackend:
    """Default backend backed by the stdlib :mod:`webbrowser` module."""

    def open(self, url: str) -> ProcessLaunchOutcome:
        try:
            opened = webbrowser.open(url, new=2, autoraise=True)
        except webbrowser.Error as exc:
            return ProcessLaunchOutcome(
                success=False,
                detail=f"webbrowser.Error: {exc}",
                backend="webbrowser",
            )
        except Exception as exc:  # pragma: no cover — defensive
            return ProcessLaunchOutcome(
                success=False,
                detail=f"unexpected: {exc}",
                backend="webbrowser",
            )
        if opened:
            return ProcessLaunchOutcome(
                success=True,
                detail="opened via stdlib webbrowser",
                backend="webbrowser",
            )
        return ProcessLaunchOutcome(
            success=False,
            detail="webbrowser.open returned False",
            backend="webbrowser",
        )


class NoopBackend:
    """Backend used when the policy decided to skip — never opens."""

    def open(self, url: str) -> ProcessLaunchOutcome:
        return ProcessLaunchOutcome(success=False, detail="noop backend", backend="noop")


class StubBackend:
    """In-memory test backend; remembers every URL it was asked to open."""

    def __init__(self, *, succeed: bool = True) -> None:
        self.calls: list[str] = []
        self.succeed = succeed

    def open(self, url: str) -> ProcessLaunchOutcome:
        self.calls.append(url)
        return ProcessLaunchOutcome(
            success=self.succeed,
            detail="stub backend",
            backend="stub",
        )


def default_backend() -> BrowserBackend:
    """Return the production-default backend."""
    return WebbrowserBackend()
