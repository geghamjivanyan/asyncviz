"""Static wheel/sdist artifact validators.

These helpers run on a *built* artifact (``dist/*.whl`` or
``dist/*.tar.gz``) — they're consumed by the release-check script and
the smoke-test pipeline. The runtime never imports them on the hot
path; importing this module pulls in :mod:`zipfile` + :mod:`tarfile`
which is fine for tooling but bloats startup.

The validator is intentionally schema-driven so adding a new
must-have file is a one-line change.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ── Schema ──────────────────────────────────────────────────────────────

#: Files that must always be present in a wheel.
_REQUIRED_WHEEL_FILES = (
    "asyncviz/__init__.py",
    "asyncviz/__main__.py",
    "asyncviz/py.typed",
    "asyncviz/packaging/__init__.py",
    "asyncviz/dashboard/__init__.py",
    "asyncviz/dashboard/static/index.html",
)

#: Glob-style prefixes that should contain *at least* one file. Useful
#: for catching "the frontend wasn't built" mistakes early.
_REQUIRED_WHEEL_PREFIXES = ("asyncviz/dashboard/static/assets/",)

#: Sdist must ship the source tree + the embedded static directory.
_REQUIRED_SDIST_FILES = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "asyncviz/__init__.py",
    "asyncviz/packaging/__init__.py",
    "asyncviz/dashboard/static/index.html",
)

Severity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class WheelValidationIssue:
    """One problem detected during validation."""

    severity: Severity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class WheelValidationReport:
    """Result of validating one artifact."""

    artifact: Path
    artifact_kind: Literal["wheel", "sdist"]
    total_files: int
    static_files: int
    issues: tuple[WheelValidationIssue, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def warnings(self) -> tuple[WheelValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")

    @property
    def errors(self) -> tuple[WheelValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")


# ── Wheel ───────────────────────────────────────────────────────────────


def validate_wheel(path: Path) -> WheelValidationReport:
    """Inspect a built ``.whl`` for completeness."""
    issues: list[WheelValidationIssue] = []
    if not path.is_file():
        return WheelValidationReport(
            artifact=path,
            artifact_kind="wheel",
            total_files=0,
            static_files=0,
            issues=(WheelValidationIssue("error", "missing", f"wheel not found: {path}"),),
        )
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as exc:
        return WheelValidationReport(
            artifact=path,
            artifact_kind="wheel",
            total_files=0,
            static_files=0,
            issues=(
                WheelValidationIssue("error", "corrupt", f"wheel is not a valid zip: {exc}"),
            ),
        )

    name_set = set(names)
    for required in _REQUIRED_WHEEL_FILES:
        if required not in name_set:
            issues.append(
                WheelValidationIssue("error", "missing-file", f"wheel missing {required}"),
            )
    for prefix in _REQUIRED_WHEEL_PREFIXES:
        if not any(n.startswith(prefix) for n in name_set):
            issues.append(
                WheelValidationIssue(
                    "error",
                    "missing-prefix",
                    f"wheel missing files under {prefix}",
                ),
            )
    if not any(n.startswith("asyncviz/dashboard/static/") for n in name_set):
        issues.append(
            WheelValidationIssue(
                "error",
                "missing-static",
                "wheel does not include the embedded frontend bundle",
            ),
        )
    static_files = sum(1 for n in name_set if n.startswith("asyncviz/dashboard/static/"))
    return WheelValidationReport(
        artifact=path,
        artifact_kind="wheel",
        total_files=len(name_set),
        static_files=static_files,
        issues=tuple(issues),
    )


# ── Sdist ───────────────────────────────────────────────────────────────


def validate_sdist(path: Path) -> WheelValidationReport:
    """Inspect a built ``.tar.gz`` for completeness."""
    issues: list[WheelValidationIssue] = []
    if not path.is_file():
        return WheelValidationReport(
            artifact=path,
            artifact_kind="sdist",
            total_files=0,
            static_files=0,
            issues=(WheelValidationIssue("error", "missing", f"sdist not found: {path}"),),
        )
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
    except (tarfile.TarError, OSError) as exc:
        return WheelValidationReport(
            artifact=path,
            artifact_kind="sdist",
            total_files=0,
            static_files=0,
            issues=(
                WheelValidationIssue("error", "corrupt", f"sdist is not a valid tarball: {exc}"),
            ),
        )

    files = [m.name for m in members if m.isfile()]
    # Sdists prefix every entry with ``<name>-<version>/`` — strip the
    # leading component so the schema stays version-agnostic.
    stripped = [_strip_sdist_prefix(name) for name in files]
    name_set = set(stripped)
    for required in _REQUIRED_SDIST_FILES:
        if required not in name_set:
            issues.append(
                WheelValidationIssue("error", "missing-file", f"sdist missing {required}"),
            )
    if not any(n.startswith("asyncviz/dashboard/static/") for n in name_set):
        issues.append(
            WheelValidationIssue(
                "error",
                "missing-static",
                "sdist does not include the embedded frontend bundle",
            ),
        )
    static_files = sum(1 for n in name_set if n.startswith("asyncviz/dashboard/static/"))
    return WheelValidationReport(
        artifact=path,
        artifact_kind="sdist",
        total_files=len(name_set),
        static_files=static_files,
        issues=tuple(issues),
    )


# ── Helpers ─────────────────────────────────────────────────────────────


def _strip_sdist_prefix(name: str) -> str:
    """Strip the leading ``<name>-<version>/`` directory from an sdist member."""
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else parts[0]


# Re-exported for callers that already hold an open archive (the
# release-check script reuses the validators on in-memory buffers).
__all__ = [
    "WheelValidationIssue",
    "WheelValidationReport",
    "validate_sdist",
    "validate_wheel",
]


def _validate_zip_bytes(  # pragma: no cover
    payload: bytes,
    *,
    artifact: Path,
) -> WheelValidationReport:
    """Defensive in-memory hook — wires the validator to a zip blob."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
    issues: list[WheelValidationIssue] = []
    name_set = set(names)
    for required in _REQUIRED_WHEEL_FILES:
        if required not in name_set:
            issues.append(WheelValidationIssue("error", "missing-file", f"missing {required}"))
    return WheelValidationReport(
        artifact=artifact,
        artifact_kind="wheel",
        total_files=len(name_set),
        static_files=sum(1 for n in name_set if n.startswith("asyncviz/dashboard/static/")),
        issues=tuple(issues),
    )
