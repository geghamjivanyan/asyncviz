#!/usr/bin/env python3
"""Enumerate the frontend assets inside a built wheel / sdist.

Routes through :func:`inspect_wheel` / :func:`inspect_sdist` so the
same logic powers the CLI tooling + ``release_checks``.

Usage:

    python scripts/packaging/inspect_wheel_assets.py            # walks dist/
    python scripts/packaging/inspect_wheel_assets.py dist/asyncviz-0.1.0-py3-none-any.whl
    python scripts/packaging/inspect_wheel_assets.py --json dist/*.whl
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from asyncviz.dashboard.assets import (
    WheelAssetReport,
    inspect_sdist,
    inspect_wheel,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = REPO_ROOT / "dist"


def _collect(paths: list[Path]) -> list[Path]:
    if paths:
        return paths
    if not DIST_DIR.is_dir():
        raise SystemExit(f"no artifacts and no dist/ directory at {DIST_DIR}")
    return sorted(
        [p for p in DIST_DIR.iterdir() if p.suffix == ".whl" or p.name.endswith(".tar.gz")],
    )


def _inspect(path: Path) -> WheelAssetReport:
    if path.suffix == ".whl":
        return inspect_wheel(path)
    if path.name.endswith(".tar.gz"):
        return inspect_sdist(path)
    raise SystemExit(f"unsupported artifact type: {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect frontend assets inside an artifact.")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--json", dest="emit_json", action="store_true")
    args = parser.parse_args()

    artifacts = _collect(args.paths)
    reports = [_inspect(path) for path in artifacts]

    if args.emit_json:
        payload = [
            {
                "artifact": str(report.artifact),
                "kind": report.kind,
                "total_files": report.total_files,
                "static_count": report.static_count,
                "has_index": report.has_index,
                "has_manifest": report.has_manifest,
                "entries": [asdict(entry) for entry in report.static_entries],
                "notes": list(report.notes),
            }
            for report in reports
        ]
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    any_missing = False
    for report in reports:
        status = "✓" if report.has_index else "✗"
        print(
            f"{status} {report.artifact.name} ({report.kind}): "
            f"{report.static_count} static, "
            f"index={'yes' if report.has_index else 'no'}, "
            f"manifest={'yes' if report.has_manifest else 'no'}",
            flush=True,
        )
        if not report.has_index:
            any_missing = True
    return 0 if not any_missing else 1


if __name__ == "__main__":
    sys.exit(main())
