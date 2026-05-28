#!/usr/bin/env python3
"""Run the canonical frontend-asset publishing pipeline.

Routes through :class:`asyncviz.dashboard.assets.FrontendAssetPublisher`
so every step (build, embed, manifest, validate) is the same code
the diagnostics endpoint + tests use.

Usage:

    python scripts/packaging/publish_frontend_assets.py
    python scripts/packaging/publish_frontend_assets.py --skip-build
    python scripts/packaging/publish_frontend_assets.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from asyncviz.dashboard.assets import (
    FrontendAssetPublisher,
    NoopBuilder,
    NpmFrontendBuilder,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
STATIC_DIR = REPO_ROOT / "asyncviz" / "dashboard" / "static"


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish the AsyncViz frontend bundle.")
    parser.add_argument("--skip-build", action="store_true", help="Skip the vite build step.")
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Skip the wipe-previous-embed step.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the manifest without writing.",
    )
    args = parser.parse_args()

    builder = NoopBuilder() if args.skip_build else NpmFrontendBuilder()
    publisher = FrontendAssetPublisher(
        repo_root=REPO_ROOT,
        static_dir=STATIC_DIR,
        frontend_dir=FRONTEND_DIR,
        builder=builder,
    )
    result = publisher.publish(
        skip_build=args.skip_build,
        skip_clean=args.skip_clean,
        dry_run=args.dry_run,
    )

    for note in result.notes:
        print(f"• {note}", flush=True)
    if result.manifest is not None:
        print(
            f"• manifest: {result.manifest.total_files} files, "
            f"{result.manifest.total_bytes} bytes, "
            f"version={result.manifest.frontend_version}",
            flush=True,
        )
    for issue in result.validation.errors:
        print(f"✗ {issue.code}: {issue.message}", flush=True)
    for issue in result.validation.warnings:
        print(f"⚠ {issue.code}: {issue.message}", flush=True)
    if not result.success:
        print("✗ publish failed", flush=True)
        return 1
    print(f"✓ published {result.files_copied} files into {result.static_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
