"""Signal forwarding + graceful shutdown for the subprocess.

The CLI installs a small ``SignalForwarder`` once per ``run``
invocation. On SIGINT/SIGTERM it forwards the signal to the child +
remembers the request so the launcher can escalate to SIGKILL after
the shutdown timeout.

Windows note: SIGTERM doesn't really exist on Windows; we send
``CTRL_BREAK_EVENT`` via :meth:`subprocess.Popen.terminate` which
talks to the child's process group on Windows when we spawn with
``creationflags=subprocess.CREATE_NEW_PROCESS_GROUP``.
"""

from __future__ import annotations

import signal
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from subprocess import Popen
from types import FrameType

_SIGNALS_TO_FORWARD: tuple[int, ...] = (
    signal.SIGINT,
    *((signal.SIGTERM,) if sys.platform != "win32" else ()),
)


@dataclass(slots=True)
class SignalForwarder:
    """Forward signals from the parent CLI to the child subprocess.

    Tracks the number of forwards so the launcher can decide when to
    escalate (1st Ctrl-C → graceful, 2nd → SIGKILL).
    """

    process: Popen[bytes]
    forwarded_count: int = 0
    last_signal: int | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _previous: dict[int, signal.Handlers | None] = field(default_factory=dict, repr=False)

    def forward(self, sig: int) -> None:
        with self._lock:
            self.forwarded_count += 1
            self.last_signal = sig
        if self.process.poll() is not None:
            return
        try:
            # ``send_signal`` is the cross-platform way; on Windows it
            # only supports CTRL_C_EVENT / CTRL_BREAK_EVENT / SIGTERM
            # (latter mapped to TerminateProcess), all of which are
            # adequate for a graceful-stop attempt.
            self.process.send_signal(sig)
        except (ProcessLookupError, OSError):
            # Child already died — no-op.
            return

    def _install_handlers(self) -> None:
        for sig in _SIGNALS_TO_FORWARD:
            previous = signal.signal(sig, self._handler)
            self._previous[sig] = previous

    def _restore_handlers(self) -> None:
        for sig, previous in self._previous.items():
            if previous is not None:
                signal.signal(sig, previous)
        self._previous.clear()

    def _handler(self, sig: int, _frame: FrameType | None) -> None:
        self.forward(sig)


@contextmanager
def install_signal_forwarder(process: Popen[bytes]) -> Iterator[SignalForwarder]:
    """Context manager that wires + restores the signal handlers."""
    forwarder = SignalForwarder(process=process)
    forwarder._install_handlers()
    try:
        yield forwarder
    finally:
        forwarder._restore_handlers()
