"""Typed metadata records written into the bundle's ``meta/`` directory.

Separating the metadata types from the writer makes the on-disk
schema easy to evolve — tests + the validator both reference these
classes directly.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from asyncviz.runtime.replay.artifacts.replay_layout import (
    META_DIRECTORY,
    PACKAGING_META_FILENAME,
    RECORDER_META_FILENAME,
    RUNTIME_META_FILENAME,
)
from asyncviz.runtime.replay.recorder.replay_integrity import atomic_write_text


@dataclass(frozen=True, slots=True)
class RuntimeMeta:
    """Identifying metadata for one runtime + target combination."""

    runtime_id: str
    asyncviz_version: str
    started_at_wall_iso: str
    finished_at_wall_iso: str | None
    started_at_monotonic_ns: int
    finished_at_monotonic_ns: int | None
    host: str
    port: int
    target: dict[str, Any]
    """Free-form description of the launched target (kind/value/argv)."""
    extras: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PackagingMeta:
    """Snapshot of the packaging diagnostics at recording time."""

    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RecorderMeta:
    """Recorder-side configuration + final statistics."""

    config: dict[str, Any]
    statistics: dict[str, Any]
    metrics: dict[str, Any]


def write_meta(
    bundle_dir: Path,
    *,
    runtime: RuntimeMeta,
    packaging: PackagingMeta | None,
    recorder: RecorderMeta,
) -> None:
    """Persist every meta record under ``bundle_dir/meta/``."""
    meta_dir = bundle_dir / META_DIRECTORY
    meta_dir.mkdir(parents=True, exist_ok=True)
    _write_json(meta_dir / RUNTIME_META_FILENAME, asdict(runtime))
    if packaging is not None:
        _write_json(meta_dir / PACKAGING_META_FILENAME, packaging.payload)
    _write_json(
        meta_dir / RECORDER_META_FILENAME,
        {
            "config": recorder.config,
            "statistics": recorder.statistics,
            "metrics": recorder.metrics,
        },
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    atomic_write_text(path, encoded)
