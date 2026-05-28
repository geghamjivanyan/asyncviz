#!/usr/bin/env python3
"""Run the production frontend build + embed it into the package.

Thin Python wrapper over the canonical shell pipeline:

  1. ``npm run build``  — emits ``frontend/dist``.
  2. ``cp -R dist/. asyncviz/dashboard/static/`` — embed the bundle.
  3. ``verify-static.sh`` — sanity-check the embed.

Reproducing the orchestration in Python lets CI workflows + release
scripts call one entry point regardless of platform (Windows runners
don't have bash). The pipeline still defers to the bash scripts when
they're available so behaviour stays identical between the two
paths.

Usage:

    python scripts/packaging/build_frontend.py
    python scripts/packaging/build_frontend.py --skip-verify
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
STATIC_DIR = REPO_ROOT / "asyncviz" / "dashboard" / "static"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """Subprocess wrapper that streams output + raises on failure."""
    print(f"  $ {' '.join(cmd)} (cwd={cwd or REPO_ROOT})", flush=True)
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if result.returncode != 0:
        raise SystemExit(f"command failed (exit {result.returncode}): {' '.join(cmd)}")


def _ensure_npm() -> None:
    if shutil.which("npm") is None:
        raise SystemExit("npm is required to build the frontend but was not found on PATH")


def _build_frontend() -> None:
    _ensure_npm()
    if not (FRONTEND_DIR / "node_modules").is_dir():
        print("• installing npm dependencies", flush=True)
        _run(["npm", "ci"], cwd=FRONTEND_DIR)
    print("• running vite production build", flush=True)
    _run(["npm", "run", "--silent", "build"], cwd=FRONTEND_DIR)
    if not (DIST_DIR / "index.html").is_file():
        raise SystemExit(f"build did not produce {DIST_DIR / 'index.html'}")


def _embed_frontend() -> None:
    if not (DIST_DIR / "index.html").is_file():
        raise SystemExit(
            f"no frontend build at {DIST_DIR}; "
            f"run the build before embedding.",
        )
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    # Wipe the previous embed but preserve the .gitkeep marker so the
    # directory survives a fresh checkout.
    for entry in STATIC_DIR.iterdir():
        if entry.name == ".gitkeep":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    print(f"• copying {DIST_DIR} → {STATIC_DIR}", flush=True)
    for entry in DIST_DIR.iterdir():
        dest = STATIC_DIR / entry.name
        if entry.is_dir():
            shutil.copytree(entry, dest)
        else:
            shutil.copy2(entry, dest)


def _verify() -> None:
    """Verify the embed via the canonical packaging asset resolver."""
    from asyncviz.packaging import locate_frontend_bundle

    resolution = locate_frontend_bundle()
    if not resolution.is_embedded:
        raise SystemExit(
            f"verification failed; missing files: {resolution.missing!r}",
        )
    print(
        f"• verified embed at {resolution.bundle_dir} "
        f"(shape={resolution.install_shape.kind}, "
        f"via={resolution.resolved_via})",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build + embed the AsyncViz frontend.")
    parser.add_argument(
        "--skip-build", action="store_true", help="Skip the vite build step (use existing dist).",
    )
    parser.add_argument(
        "--skip-embed", action="store_true", help="Skip the copy-into-package step.",
    )
    parser.add_argument(
        "--skip-verify", action="store_true", help="Skip the post-embed verification step.",
    )
    args = parser.parse_args()

    if not args.skip_build:
        print("▸ build frontend", flush=True)
        _build_frontend()
    if not args.skip_embed:
        print("▸ embed frontend", flush=True)
        _embed_frontend()
    if not args.skip_verify:
        print("▸ verify embed", flush=True)
        _verify()
    print("✓ frontend ready for packaging", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
