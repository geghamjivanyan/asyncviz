"""Open-once session guard for the browser launcher.

Repeated CLI runs (or signal-driven restarts) would otherwise spawn a
new browser tab every time. The session guard tracks "we already
opened a tab for this session id" so a dev-loop Ctrl-C + restart
re-uses the existing tab.

The guard is process-local — the user's browser ultimately decides
tab reuse, but we at least don't *issue* a redundant open.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass(slots=True)
class BrowserSessionGuard:
    """In-process registry of session-ids that have already been opened."""

    _opened: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def should_open(self, session_id: str | None) -> bool:
        """Return True if this session has not been opened yet.

        ``session_id is None`` means "no dedup" — every call returns
        True. That's the default when the CLI hasn't supplied a
        runtime-id.
        """
        if session_id is None:
            return True
        with self._lock:
            if session_id in self._opened:
                return False
            self._opened.add(session_id)
            return True

    def reset(self, session_id: str | None = None) -> None:
        """Clear ``session_id`` (or every id when ``None``)."""
        with self._lock:
            if session_id is None:
                self._opened.clear()
            else:
                self._opened.discard(session_id)

    def __contains__(self, session_id: object) -> bool:
        with self._lock:
            return session_id in self._opened


#: Process-wide guard used by :class:`BrowserLauncher`. Exposed for
#: tests + diagnostics.
_default_guard = BrowserSessionGuard()


def get_default_session_guard() -> BrowserSessionGuard:
    return _default_guard


def reset_default_session_guard() -> None:
    _default_guard.reset()
