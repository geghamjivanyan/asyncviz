"""Subprocess spawn + wait abstraction.

Keeps every call to :mod:`subprocess` in one place so cross-platform
quirks (Windows process groups, signal propagation) live next to
each other instead of leaking into the launcher.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from asyncviz.cli.runtime.diagnostics import record_lifecycle_event
from asyncviz.cli.runtime.lifecycle import (
    install_signal_forwarder,
)
from asyncviz.cli.runtime.observability import get_cli_metrics


@dataclass(frozen=True, slots=True)
class SubprocessOutcome:
    """Result of running the subprocess to completion."""

    return_code: int
    duration_seconds: float
    signal_forwards: int
    timed_out_at_shutdown: bool
    last_signal: int | None


class SubprocessRunner:
    """Spawn a subprocess + wait for it with signal forwarding + cleanup."""

    def __init__(self, *, shutdown_timeout: float, kill_grace: float = 2.0) -> None:
        self.shutdown_timeout = max(0.0, shutdown_timeout)
        self.kill_grace = max(0.0, kill_grace)

    def run(
        self,
        argv: list[str],
        *,
        env: Mapping[str, str],
        cwd: Path | None = None,
    ) -> SubprocessOutcome:
        """Spawn ``argv`` with the supplied env + cwd; return when it exits."""
        record_lifecycle_event("subprocess-spawn", " ".join(argv[:3]))
        get_cli_metrics().record_subprocess_launch()
        creationflags = 0
        if sys.platform == "win32":
            # Required so we can deliver CTRL_BREAK_EVENT cleanly.
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        started_at = time.monotonic()
        process = subprocess.Popen(
            argv,
            env=dict(env),
            cwd=str(cwd) if cwd is not None else None,
            creationflags=creationflags,
            # Inherit stdin/stdout/stderr so the user's program looks
            # native to them — no pipe wrapping, no buffering surprises.
            stdin=None,
            stdout=None,
            stderr=None,
        )
        timed_out = False
        with install_signal_forwarder(process) as forwarder:
            try:
                return_code = process.wait()
            except KeyboardInterrupt:
                # The forwarder already delivered a SIGINT — we just
                # need to wait for the child to exit, with escalation.
                return_code, timed_out = self._await_with_shutdown(process)
            else:
                # Normal exit; ensure no further signal arrives in the
                # process group while we measure timings.
                pass
            if forwarder.last_signal is not None and process.poll() is None:
                return_code, timed_out = self._await_with_shutdown(process)

            signal_forwards = forwarder.forwarded_count
            last_signal = forwarder.last_signal

        duration = time.monotonic() - started_at
        if signal_forwards > 0:
            get_cli_metrics().record_signal_forward()
        record_lifecycle_event(
            "subprocess-exit",
            f"code={return_code} forwards={signal_forwards} duration={duration:.2f}s",
        )
        return SubprocessOutcome(
            return_code=return_code if return_code is not None else 1,
            duration_seconds=duration,
            signal_forwards=signal_forwards,
            timed_out_at_shutdown=timed_out,
            last_signal=last_signal,
        )

    def _await_with_shutdown(
        self,
        process: subprocess.Popen[bytes],
    ) -> tuple[int, bool]:
        """Wait for ``process`` after sending a graceful signal.

        Returns ``(return_code, timed_out)``. When the wait exceeds
        ``shutdown_timeout`` we escalate to ``terminate`` + ``kill``
        and report ``timed_out=True`` so the launcher can log it.
        """
        try:
            return process.wait(timeout=self.shutdown_timeout), False
        except subprocess.TimeoutExpired:
            record_lifecycle_event("shutdown-escalation", "graceful timed out")
            process.terminate()
            try:
                return process.wait(timeout=self.kill_grace), True
            except subprocess.TimeoutExpired:
                process.kill()
                return process.wait(), True
