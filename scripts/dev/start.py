#!/usr/bin/env python3
"""Run backend + frontend dev servers with prefixed output and clean shutdown."""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

LABEL_COLORS = {
    "backend": "\033[36m",  # cyan
    "frontend": "\033[35m",  # magenta
}
RESET = "\033[0m"
USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _paint(label: str) -> str:
    if not USE_COLOR:
        return f"[{label}]"
    color = LABEL_COLORS.get(label, "")
    return f"{color}[{label}]{RESET}"


def _detect_python() -> str:
    override = os.environ.get("ASYNCVIZ_PYTHON")
    if override:
        return override
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    fallback = shutil.which("python3")
    if fallback is None:
        sys.exit("error: python3 not found on PATH; run `make install` first")
    return fallback


def _spawn(command: list[str], cwd: Path, label: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _pump(proc: subprocess.Popen[bytes], label: str) -> None:
    prefix = (_paint(label) + " ").encode()
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, b""):
        sys.stdout.buffer.write(prefix + line)
        sys.stdout.buffer.flush()


def _shutdown(procs: list[subprocess.Popen[bytes]], grace: float = 6.0) -> None:
    for proc in procs:
        if proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGINT)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and any(p.poll() is None for p in procs):
        time.sleep(0.05)
    for proc in procs:
        if proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--frontend-only", action="store_true")
    args = parser.parse_args()

    if args.backend_only and args.frontend_only:
        sys.exit("error: pass at most one of --backend-only / --frontend-only")

    python = _detect_python()
    npm = shutil.which("npm")
    if npm is None and not args.backend_only:
        sys.exit("error: npm not found on PATH; install Node.js 20+")

    procs: list[subprocess.Popen[bytes]] = []
    threads: list[threading.Thread] = []

    if not args.frontend_only:
        env = os.environ.copy()
        env.setdefault("ASYNCVIZ_OPEN_BROWSER", "false")
        proc = subprocess.Popen(
            [python, "-m", "asyncviz"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
        procs.append(proc)
        t = threading.Thread(target=_pump, args=(proc, "backend"), daemon=True)
        t.start()
        threads.append(t)

    if not args.backend_only:
        assert npm is not None
        proc = _spawn([npm, "run", "dev"], ROOT / "frontend", "frontend")
        procs.append(proc)
        t = threading.Thread(target=_pump, args=(proc, "frontend"), daemon=True)
        t.start()
        threads.append(t)

    def _handle(_signum: int, _frame: object) -> None:
        _shutdown(procs)

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    exit_code = 0
    try:
        while True:
            alive = [p for p in procs if p.poll() is None]
            for p in procs:
                rc = p.poll()
                if rc is not None and rc != 0 and exit_code == 0:
                    exit_code = rc
            if not alive:
                break
            if len(alive) < len(procs):
                _shutdown(procs)
                break
            time.sleep(0.1)
    finally:
        _shutdown(procs, grace=2.0)
        for t in threads:
            t.join(timeout=2.0)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
