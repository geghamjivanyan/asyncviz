"""Tiny CLI output helpers.

The CLI deliberately avoids pulling in ``rich`` / ``colorama`` so the
wheel stays light and Windows-friendly. Anything that needs more
formatting than these helpers provide should reach for ``logging`` so
the diagnostics machinery picks it up.

Colour rules:

* Enabled when stderr is a TTY AND ``NO_COLOR`` is unset AND
  ``ASYNCVIZ_NO_COLOR`` is unset.
* Disabled in CI / pipes by default.
* Tests can force enable/disable via :func:`set_color_enabled`.
"""

from __future__ import annotations

import os
import sys
from typing import TextIO

_FORCED: bool | None = None


def _stream_is_tty(stream: TextIO) -> bool:
    try:
        return stream.isatty()
    except Exception:
        return False


def color_enabled(stream: TextIO | None = None) -> bool:
    """Return whether colour output is permitted for ``stream``."""
    if _FORCED is not None:
        return _FORCED
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("ASYNCVIZ_NO_COLOR") is not None:
        return False
    target = stream if stream is not None else sys.stderr
    return _stream_is_tty(target)


def set_color_enabled(value: bool | None) -> None:
    """Force colour on (True), off (False), or honor env detection (None)."""
    global _FORCED
    _FORCED = value


# ── Colour primitives ──────────────────────────────────────────────────


_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"


def _wrap(value: str, code: str, *, stream: TextIO | None = None) -> str:
    if not color_enabled(stream):
        return value
    return f"{code}{value}{_RESET}"


def emit(level: str, message: str, *, stream: TextIO | None = None) -> None:
    """Write a level-prefixed line. ``level`` is one of info/ok/warn/error."""
    target = stream if stream is not None else sys.stderr
    prefix = {
        "info": _wrap("•", _DIM, stream=target),
        "ok": _wrap("✓", _GREEN, stream=target),
        "warn": _wrap("⚠", _YELLOW, stream=target),
        "error": _wrap("✗", _RED, stream=target),
        "log": _wrap("▸", _CYAN + _BOLD, stream=target),
    }.get(level, "•")
    target.write(f"{prefix} {message}\n")
    target.flush()


def info(message: str, *, stream: TextIO | None = None) -> None:
    emit("info", message, stream=stream)


def ok(message: str, *, stream: TextIO | None = None) -> None:
    emit("ok", message, stream=stream)


def warn(message: str, *, stream: TextIO | None = None) -> None:
    emit("warn", message, stream=stream)


def error(message: str, *, stream: TextIO | None = None) -> None:
    emit("error", message, stream=stream)


def log(message: str, *, stream: TextIO | None = None) -> None:
    emit("log", message, stream=stream)
