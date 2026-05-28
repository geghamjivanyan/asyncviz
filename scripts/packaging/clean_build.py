#!/usr/bin/env python3
"""Clean every packaging artifact in the repo.

Removes:

* ``dist/``                — wheels + sdists
* ``build/``               — Hatch / setuptools intermediates
* ``*.egg-info`` directories
* ``asyncviz/dashboard/static/`` contents (preserves ``.gitkeep``)
* ``frontend/dist``        — vite output

Idempotent: missing directories are silently skipped.

Usage:

    python scripts/packaging/clean_build.py
    python scripts/packaging/clean_build.py --keep-frontend
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _rm(path: Path) -> None:
    if path.is_dir():
        print(f"• removing dir  {path.relative_to(REPO_ROOT)}", flush=True)
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        print(f"• removing file {path.relative_to(REPO_ROOT)}", flush=True)
        path.unlink()


def _wipe_static() -> None:
    static = REPO_ROOT / "asyncviz" / "dashboard" / "static"
    if not static.is_dir():
        return
    for entry in static.iterdir():
        if entry.name == ".gitkeep":
            continue
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            with contextlib.suppress(OSError):
                entry.unlink()
    print(f"• cleared        {static.relative_to(REPO_ROOT)} (kept .gitkeep)", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean AsyncViz build artifacts.")
    parser.add_argument(
        "--keep-frontend",
        action="store_true",
        help="Skip wiping the embedded frontend bundle + frontend/dist.",
    )
    args = parser.parse_args()

    for entry in REPO_ROOT.iterdir():
        if entry.name in ("dist", "build") or (entry.is_dir() and entry.name.endswith(".egg-info")):
            _rm(entry)

    if not args.keep_frontend:
        _wipe_static()
        _rm(REPO_ROOT / "frontend" / "dist")

    print("✓ packaging artifacts cleaned", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
