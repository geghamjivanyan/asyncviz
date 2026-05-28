#!/usr/bin/env python3
"""Validate the published frontend bundle on disk.

Runs the canonical :func:`validate_published_bundle` over the
embedded ``asyncviz/dashboard/static`` directory and prints a
human-readable report. Exits non-zero on any error so it can gate
CI.

Usage:

    python scripts/packaging/validate_frontend_assets.py
    python scripts/packaging/validate_frontend_assets.py --json
    python scripts/packaging/validate_frontend_assets.py path/to/static
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from asyncviz.dashboard.assets import validate_published_bundle

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STATIC = REPO_ROOT / "asyncviz" / "dashboard" / "static"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the published frontend bundle.")
    parser.add_argument(
        "static_dir",
        nargs="?",
        type=Path,
        help="Override the static directory (default: asyncviz/dashboard/static).",
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit a JSON report instead of human-readable text.",
    )
    args = parser.parse_args()

    static_dir = args.static_dir or DEFAULT_STATIC
    report = validate_published_bundle(static_dir)

    if args.emit_json:
        payload = {
            "static_dir": str(report.static_dir),
            "ok": report.ok,
            "file_count": report.file_count,
            "total_bytes": report.total_bytes,
            "issues": [asdict(issue) for issue in report.issues],
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if report.ok else 1

    status = "✓" if report.ok else "✗"
    print(
        f"{status} bundle at {report.static_dir}: "
        f"{report.file_count} files, {report.total_bytes} bytes",
        flush=True,
    )
    for issue in report.errors:
        print(f"  ERROR [{issue.code}] {issue.message}", flush=True)
    for issue in report.warnings:
        print(f"  WARN  [{issue.code}] {issue.message}", flush=True)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
