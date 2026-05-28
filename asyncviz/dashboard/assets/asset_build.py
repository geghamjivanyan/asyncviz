"""Frontend build invocation helpers.

The publisher delegates the actual ``npm run build`` step here so
test cases that don't need a real build can supply a stub builder
without monkey-patching :mod:`subprocess`.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class FrontendBuilder(Protocol):
    """Strategy interface for running ``npm run build``."""

    def build(self, *, frontend_dir: Path) -> FrontendBuildOutcome:  # pragma: no cover
        ...


@dataclass(frozen=True, slots=True)
class FrontendBuildOutcome:
    success: bool
    detail: str
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""


class NpmFrontendBuilder:
    """Default builder — invokes ``npm run build`` in ``frontend_dir``."""

    def __init__(self, *, install_when_missing: bool = True, timeout: float | None = 600.0) -> None:
        self.install_when_missing = install_when_missing
        self.timeout = timeout

    def build(self, *, frontend_dir: Path) -> FrontendBuildOutcome:
        if shutil.which("npm") is None:
            return FrontendBuildOutcome(success=False, detail="npm not found on PATH")
        if self.install_when_missing and not (frontend_dir / "node_modules").is_dir():
            outcome = self._run(["npm", "ci"], cwd=frontend_dir)
            if not outcome.success:
                return outcome
        return self._run(["npm", "run", "--silent", "build"], cwd=frontend_dir)

    def _run(self, cmd: list[str], *, cwd: Path) -> FrontendBuildOutcome:
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return FrontendBuildOutcome(
                success=False,
                detail=f"command timed out after {self.timeout}s",
                stdout=str(exc.stdout or ""),
                stderr=str(exc.stderr or ""),
                return_code=-1,
            )
        success = result.returncode == 0
        return FrontendBuildOutcome(
            success=success,
            detail="ok" if success else f"command failed (exit {result.returncode})",
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )


class NoopBuilder:
    """Builder that succeeds without doing anything.

    Useful in tests that pre-populate the dist directory + want to
    exercise the publisher without invoking npm.
    """

    def build(self, *, frontend_dir: Path) -> FrontendBuildOutcome:
        return FrontendBuildOutcome(success=True, detail="noop builder")
