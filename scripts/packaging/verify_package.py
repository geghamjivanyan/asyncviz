#!/usr/bin/env python3
"""Verify a built AsyncViz artifact (wheel or sdist).

Runs the canonical :mod:`asyncviz.packaging.wheel_validation`
inspectors on every artifact in ``dist/`` (or one passed explicitly)
and prints a human-readable report. Exits non-zero on any error so it
can gate a CI release pipeline.

Usage:

    python scripts/packaging/verify_package.py            # walks dist/
    python scripts/packaging/verify_package.py dist/foo.whl
    python scripts/packaging/verify_package.py dist/foo.whl dist/foo.tar.gz
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from asyncviz.packaging import (
    WheelValidationReport,
    validate_sdist,
    validate_wheel,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DIST = REPO_ROOT / "dist"


def _collect_artifacts(paths: list[Path]) -> list[Path]:
    if paths:
        return paths
    if not DEFAULT_DIST.is_dir():
        raise SystemExit(f"no artifacts and no dist/ directory at {DEFAULT_DIST}")
    artifacts = sorted(
        [p for p in DEFAULT_DIST.iterdir() if p.suffix in (".whl",) or p.name.endswith(".tar.gz")],
        key=lambda p: p.name,
    )
    if not artifacts:
        raise SystemExit(f"no wheel or sdist artifacts in {DEFAULT_DIST}")
    return artifacts


def _validate(path: Path) -> WheelValidationReport:
    if path.suffix == ".whl":
        return validate_wheel(path)
    if path.name.endswith(".tar.gz"):
        return validate_sdist(path)
    raise SystemExit(f"unsupported artifact type: {path.name}")


def _report(report: WheelValidationReport) -> None:
    status = "✓" if report.ok else "✗"
    print(
        f"{status} {report.artifact.name} "
        f"({report.artifact_kind}, files={report.total_files}, "
        f"static={report.static_files})",
        flush=True,
    )
    for issue in report.issues:
        prefix = "  ERROR " if issue.severity == "error" else "  WARN  "
        print(f"{prefix}[{issue.code}] {issue.message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate built AsyncViz artifacts.")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    artifacts = _collect_artifacts(args.paths)

    any_failed = False
    for artifact in artifacts:
        report = _validate(artifact)
        _report(report)
        if not report.ok:
            any_failed = True
    if any_failed:
        print("✗ one or more artifacts failed validation", flush=True)
        return 1
    print(f"✓ {len(artifacts)} artifact(s) validated", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
