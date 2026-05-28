"""Ring-buffer tracer for the configuration resolver.

Disabled by default. The diagnostics layer flips it on for live
inspection; tests use it to assert "the right sources were tried in
the right order".
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

ConfigurationTraceKind = Literal[
    "resolution-start",
    "profile-applied",
    "environment-applied",
    "api-overrides-applied",
    "cli-overrides-applied",
    "validation-success",
    "validation-failed",
    "snapshot-captured",
]


@dataclass(frozen=True, slots=True)
class ConfigurationTraceEntry:
    kind: ConfigurationTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[ConfigurationTraceEntry] = deque(maxlen=_CAPACITY)


def is_configuration_trace_enabled() -> bool:
    return _enabled


def set_configuration_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_configuration_trace(kind: ConfigurationTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(
        ConfigurationTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()),
    )


def get_configuration_trace() -> tuple[ConfigurationTraceEntry, ...]:
    return tuple(_ring)


def clear_configuration_trace() -> None:
    _ring.clear()
