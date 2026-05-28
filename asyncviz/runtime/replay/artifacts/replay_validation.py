"""Static validator for a replay bundle on disk.

Used by the CLI ``--verify`` flag + by tests that want to assert a
bundle is internally consistent. Reports issues at two severities:

* ``"error"`` — the bundle is unusable.
* ``"warning"`` — the bundle is readable but something's off (e.g.
  ``INCOMPLETE`` marker still present).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from asyncviz.runtime.replay.artifacts.replay_bundle import open_bundle
from asyncviz.runtime.replay.artifacts.replay_layout import (
    ARTIFACT_SCHEMA_VERSION,
    INCOMPLETE_MARKER,
    MANIFEST_FILENAME,
)
from asyncviz.runtime.replay.recorder.replay_integrity import sha256_file

Severity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class BundleValidationIssue:
    severity: Severity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class BundleValidationReport:
    root: Path
    finalized: bool
    chunk_count: int
    event_count: int
    issues: tuple[BundleValidationIssue, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> tuple[BundleValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[BundleValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")


def validate_bundle(root: Path) -> BundleValidationReport:
    issues: list[BundleValidationIssue] = []
    if not root.is_dir():
        return BundleValidationReport(
            root=root,
            finalized=False,
            chunk_count=0,
            event_count=0,
            issues=(BundleValidationIssue("error", "missing", f"bundle not found: {root}"),),
        )
    if not (root / MANIFEST_FILENAME).is_file():
        return BundleValidationReport(
            root=root,
            finalized=False,
            chunk_count=0,
            event_count=0,
            issues=(BundleValidationIssue("error", "missing-manifest", f"no {MANIFEST_FILENAME}"),),
        )
    try:
        bundle = open_bundle(root)
    except Exception as exc:
        return BundleValidationReport(
            root=root,
            finalized=False,
            chunk_count=0,
            event_count=0,
            issues=(BundleValidationIssue("error", "bad-manifest", str(exc)),),
        )

    manifest = bundle.manifest

    if manifest.schema_version > ARTIFACT_SCHEMA_VERSION:
        issues.append(
            BundleValidationIssue(
                "error",
                "schema-too-new",
                (
                    f"manifest schema version {manifest.schema_version} "
                    f"> supported {ARTIFACT_SCHEMA_VERSION}"
                ),
            ),
        )

    if (root / INCOMPLETE_MARKER).exists():
        issues.append(
            BundleValidationIssue(
                "warning",
                "incomplete",
                f"bundle still carries {INCOMPLETE_MARKER}; recorder did not finalize cleanly",
            ),
        )
    if not manifest.finalized:
        issues.append(
            BundleValidationIssue(
                "warning",
                "not-finalized",
                "manifest reports finalized=false",
            ),
        )

    previous_end: int | None = None
    for chunk in manifest.chunks:
        path = root / chunk.file
        if not path.is_file():
            issues.append(
                BundleValidationIssue(
                    "error",
                    "missing-chunk",
                    f"chunk file missing: {chunk.file}",
                ),
            )
            continue
        actual_size = path.stat().st_size
        if actual_size != chunk.compressed_bytes:
            issues.append(
                BundleValidationIssue(
                    "error",
                    "size-mismatch",
                    f"{chunk.file}: manifest size {chunk.compressed_bytes} != actual {actual_size}",
                ),
            )
        digest = sha256_file(path)
        if digest != chunk.sha256:
            issues.append(
                BundleValidationIssue(
                    "error",
                    "hash-mismatch",
                    f"{chunk.file}: sha256 mismatch",
                ),
            )
        if chunk.sequence_end < chunk.sequence_start:
            issues.append(
                BundleValidationIssue(
                    "error",
                    "inverted-sequence",
                    f"{chunk.file}: sequence_end < sequence_start",
                ),
            )
        if previous_end is not None and chunk.sequence_start < previous_end:
            issues.append(
                BundleValidationIssue(
                    "warning",
                    "overlapping-sequence",
                    (
                        f"{chunk.file}: starts at {chunk.sequence_start} "
                        f"but previous ended at {previous_end}"
                    ),
                ),
            )
        previous_end = chunk.sequence_end

    return BundleValidationReport(
        root=root,
        finalized=manifest.finalized and not (root / INCOMPLETE_MARKER).exists(),
        chunk_count=len(manifest.chunks),
        event_count=manifest.event_count,
        issues=tuple(issues),
    )
