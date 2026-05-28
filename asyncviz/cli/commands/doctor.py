"""``asyncviz doctor`` — print a packaging + environment health report.

Combines the canonical packaging diagnostics with a handful of
CLI-side environment checks: Python version, ``sys.executable``
visibility, browser availability, etc. Everything reads from
existing modules — doctor is *just* a renderer.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict, dataclass, field

from asyncviz.cli.browser import detect_browser_availability
from asyncviz.cli.exit_codes import ExitCode
from asyncviz.cli.output import emit, error, info, ok, warn
from asyncviz.packaging import build_packaging_diagnostics


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One row of the doctor report."""

    name: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Aggregate report — bundle + checks."""

    python: dict[str, str]
    packaging: dict[str, object]
    checks: tuple[DoctorCheck, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(c.status != "error" for c in self.checks)


def _python_info() -> dict[str, str]:
    return {
        "version": sys.version.split(" ")[0],
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "platform": platform.platform(),
    }


def _build_checks() -> tuple[DoctorCheck, ...]:
    checks: list[DoctorCheck] = []

    # Python version — already gated by ``requires-python`` in
    # pyproject.toml, but a runtime check is friendlier.
    if sys.version_info >= (3, 12):  # noqa: UP036 — runtime diagnostic, not a static guard
        checks.append(DoctorCheck("python-version", "ok", f"Python {sys.version_info[:3]}"))
    else:
        checks.append(
            DoctorCheck(
                "python-version",
                "error",
                f"Python {sys.version_info[:3]} < 3.12 required",
            ),
        )

    # Packaging
    pkg = build_packaging_diagnostics()
    if pkg.bundle_present:
        checks.append(
            DoctorCheck(
                "frontend-bundle",
                "ok",
                f"{pkg.bundle_file_count} files at {pkg.bundle_dir} ({pkg.install_shape})",
            ),
        )
    else:
        checks.append(
            DoctorCheck(
                "frontend-bundle",
                "error",
                f"bundle missing {pkg.missing_files!r} at {pkg.bundle_dir}",
            ),
        )

    # Browser
    availability = detect_browser_availability()
    detail = availability.reason
    if availability.signals:
        detail = f"{detail} (signals: {', '.join(availability.signals)})"
    if availability.available:
        checks.append(DoctorCheck("browser", "ok", detail))
    else:
        # ``code`` is the stable machine-readable tag — surface it so
        # operators have a deterministic string to grep / report.
        checks.append(
            DoctorCheck("browser", "warn", f"[{availability.code}] {detail}"),
        )

    return tuple(checks)


def run(args: argparse.Namespace, **_: object) -> int:
    checks = _build_checks()
    report = DoctorReport(
        python=_python_info(),
        packaging=build_packaging_diagnostics().to_dict(),
        checks=checks,
    )

    if getattr(args, "emit_json", False):
        json.dump(
            {
                "python": report.python,
                "packaging": report.packaging,
                "checks": [asdict(c) for c in report.checks],
                "ok": report.ok,
            },
            sys.stdout,
            indent=2,
            sort_keys=True,
        )
        sys.stdout.write("\n")
        return int(ExitCode.OK if report.ok else ExitCode.GENERIC_FAILURE)

    # Human-readable rendering.
    emit("log", "AsyncViz Doctor")
    info(f"python           {report.python['version']} ({report.python['implementation']})")
    info(f"executable       {report.python['executable']}")
    info(f"platform         {report.python['platform']}")
    info(f"asyncviz version {report.packaging['version']}")
    info(
        f"bundle           {report.packaging['bundle_dir']} "
        f"({report.packaging['install_shape']})",
    )
    info(f"manifest source  {report.packaging['manifest_source']}")
    print("", flush=True)

    for check in report.checks:
        if check.status == "ok":
            ok(f"{check.name}: {check.detail}")
        elif check.status == "warn":
            warn(f"{check.name}: {check.detail}")
        else:
            error(f"{check.name}: {check.detail}")

    return int(ExitCode.OK if report.ok else ExitCode.GENERIC_FAILURE)
