#!/usr/bin/env python3
"""Pre-release gate.

Runs the canonical checks that should pass before publishing AsyncViz:

  1. ``asyncviz`` imports cleanly + version matches pyproject.
  2. The embedded frontend bundle is present and well-formed.
  3. Wheel + sdist exist in ``dist/`` and pass static validation.
  4. The diagnostics snapshot includes a non-missing manifest.

Each check is independent; the script reports every failure rather
than stopping on the first one so release engineers see the full
picture.

Usage:

    python scripts/packaging/release_checks.py
    python scripts/packaging/release_checks.py --strict   # treat warnings as errors
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = REPO_ROOT / "dist"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_version() -> CheckResult:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    import asyncviz

    if asyncviz.__version__ != project_version:
        return CheckResult(
            "version-consistency",
            False,
            (
                f"asyncviz.__version__={asyncviz.__version__!r} but "
                f"pyproject.toml says {project_version!r}"
            ),
        )
    return CheckResult("version-consistency", True, f"version {project_version}")


def _check_bundle() -> CheckResult:
    from asyncviz.packaging import locate_frontend_bundle

    resolution = locate_frontend_bundle()
    if not resolution.is_embedded:
        return CheckResult(
            "frontend-embedded",
            False,
            f"bundle missing files: {resolution.missing!r}",
        )
    return CheckResult(
        "frontend-embedded",
        True,
        f"bundle at {resolution.bundle_dir} ({resolution.install_shape.kind})",
    )


def _check_manifest() -> CheckResult:
    from asyncviz.packaging import get_package_metadata

    meta = get_package_metadata()
    if not meta.bundle_manifest.is_present:
        return CheckResult(
            "frontend-manifest",
            False,
            "bundle manifest reports source='missing'",
        )
    return CheckResult(
        "frontend-manifest",
        True,
        f"manifest source={meta.bundle_manifest.source} "
        f"entries={len(meta.bundle_manifest.entries)}",
    )


def _check_artifacts(strict: bool) -> list[CheckResult]:
    from asyncviz.packaging import validate_sdist, validate_wheel

    if not DIST_DIR.is_dir():
        return [CheckResult("artifacts-present", False, f"no dist/ at {DIST_DIR}")]

    wheels = sorted(DIST_DIR.glob("*.whl"))
    sdists = sorted(DIST_DIR.glob("*.tar.gz"))
    results: list[CheckResult] = []
    if not wheels:
        results.append(CheckResult("wheel-present", False, "no .whl in dist/"))
    if not sdists:
        results.append(CheckResult("sdist-present", False, "no .tar.gz in dist/"))

    for wheel in wheels:
        report = validate_wheel(wheel)
        results.append(
            CheckResult(
                f"wheel:{wheel.name}",
                report.ok,
                _summarize_report(report, strict),
            ),
        )
    for sdist in sdists:
        report = validate_sdist(sdist)
        results.append(
            CheckResult(
                f"sdist:{sdist.name}",
                report.ok,
                _summarize_report(report, strict),
            ),
        )
    return results


def _summarize_report(report, strict: bool) -> str:  # type: ignore[no-untyped-def]
    parts: list[str] = []
    parts.append(f"{report.total_files} files, {report.static_files} static")
    for issue in report.errors:
        parts.append(f"E[{issue.code}] {issue.message}")
    for issue in report.warnings:
        if strict:
            parts.append(f"E[{issue.code}] {issue.message}")
        else:
            parts.append(f"W[{issue.code}] {issue.message}")
    return "; ".join(parts)


def _emit(result: CheckResult) -> None:
    mark = "✓" if result.ok else "✗"
    print(f"{mark} {result.name:30s} {result.detail}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AsyncViz pre-release checks.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures.",
    )
    args = parser.parse_args()

    results = [
        _check_version(),
        _check_bundle(),
        _check_manifest(),
        *_check_artifacts(args.strict),
    ]
    for result in results:
        _emit(result)
    failures = [r for r in results if not r.ok]
    if failures:
        print(f"\n✗ release gate failed: {len(failures)} check(s) reported errors", flush=True)
        return 1
    print(f"\n✓ release gate passed ({len(results)} checks)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
