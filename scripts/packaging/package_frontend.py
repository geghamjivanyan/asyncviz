#!/usr/bin/env python3
"""Build wheel + sdist after ensuring the frontend is embedded.

Wraps ``python -m build`` so the frontend is rebuilt and embedded
before each artifact is produced. Re-runs are idempotent: if the
embed already exists and ``--no-rebuild`` is passed, the frontend
step is skipped.

Usage:

    python scripts/packaging/package_frontend.py
    python scripts/packaging/package_frontend.py --no-rebuild
    python scripts/packaging/package_frontend.py --wheel-only
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = REPO_ROOT / "dist"


def _run(cmd: list[str]) -> None:
    print(f"  $ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(f"command failed (exit {result.returncode}): {' '.join(cmd)}")


def _ensure_build_module(python: str) -> None:
    result = subprocess.run(
        [python, "-c", "import build"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        print("• installing build module", flush=True)
        _run([python, "-m", "pip", "install", "--quiet", "build>=1.2"])


def _ensure_frontend(skip: bool) -> None:
    if skip:
        return
    from asyncviz.packaging import locate_frontend_bundle

    resolution = locate_frontend_bundle()
    if resolution.is_embedded:
        print(f"• reusing existing embed at {resolution.bundle_dir}", flush=True)
        return
    print("• embed missing — building frontend", flush=True)
    script = REPO_ROOT / "scripts" / "packaging" / "build_frontend.py"
    _run([sys.executable, str(script)])


def _clean_dist() -> None:
    if DIST_DIR.is_dir():
        for entry in DIST_DIR.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    DIST_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AsyncViz wheel + sdist artifacts.")
    parser.add_argument(
        "--no-rebuild",
        action="store_true",
        help="Skip the frontend rebuild if the embed already exists.",
    )
    parser.add_argument(
        "--wheel-only",
        action="store_true",
        help="Build only the wheel artifact.",
    )
    parser.add_argument(
        "--sdist-only",
        action="store_true",
        help="Build only the sdist artifact.",
    )
    parser.add_argument(
        "--keep-dist",
        action="store_true",
        help="Do not wipe dist/ before building.",
    )
    args = parser.parse_args()

    _ensure_frontend(skip=args.no_rebuild)
    _ensure_build_module(sys.executable)
    if not args.keep_dist:
        print("• clearing dist/", flush=True)
        _clean_dist()

    build_args = [sys.executable, "-m", "build", "--outdir", str(DIST_DIR)]
    if args.wheel_only:
        build_args.append("--wheel")
    elif args.sdist_only:
        build_args.append("--sdist")
    print("▸ build artifacts", flush=True)
    _run(build_args)

    # Final verification — fail fast on a broken artifact.
    verify_script = REPO_ROOT / "scripts" / "packaging" / "verify_package.py"
    print("▸ verify artifacts", flush=True)
    _run([sys.executable, str(verify_script)])

    print("✓ package build complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
