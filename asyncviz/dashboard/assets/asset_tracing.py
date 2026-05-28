"""Ring-buffer tracer for the asset subsystem."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

AssetTraceKind = Literal[
    "publish-start",
    "publish-clean",
    "publish-copy",
    "publish-manifest",
    "publish-validate",
    "publish-finished",
    "publish-failed",
    "validation-run",
    "validation-issue",
    "resolution-refresh",
    "cache-hit",
    "cache-miss",
]


@dataclass(frozen=True, slots=True)
class AssetTraceEntry:
    kind: AssetTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[AssetTraceEntry] = deque(maxlen=_CAPACITY)


def is_asset_trace_enabled() -> bool:
    return _enabled


def set_asset_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_asset_trace(kind: AssetTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(AssetTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()))


def get_asset_trace() -> tuple[AssetTraceEntry, ...]:
    return tuple(_ring)


def clear_asset_trace() -> None:
    _ring.clear()
