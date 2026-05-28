"""Typed primitives consumed by the env-config loader.

Splits the value types from the parsing logic so callers can pattern-
match on a ``ParseOutcome`` without dragging the parser implementations
into their import graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class ParseKind(StrEnum):
    """What kind of value the parser produces."""

    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    DURATION_SECONDS = "duration_seconds"
    DURATION_MS = "duration_ms"
    PATH = "path"
    ENUM = "enum"
    LIST = "list"


@dataclass(frozen=True, slots=True)
class ParseOutcome:
    """Result of one env-var parse attempt.

    Carries both the resolved value (when successful) + the raw
    input + a structured error so callers can render a useful
    diagnostic.
    """

    ok: bool
    value: Any
    raw: str
    kind: ParseKind
    error: str | None = None
    """``None`` when ``ok=True``; otherwise a one-line failure reason."""

    @classmethod
    def success(cls, *, value: Any, raw: str, kind: ParseKind) -> ParseOutcome:
        return cls(ok=True, value=value, raw=raw, kind=kind, error=None)

    @classmethod
    def failure(cls, *, raw: str, kind: ParseKind, error: str) -> ParseOutcome:
        return cls(ok=False, value=None, raw=raw, kind=kind, error=error)


Severity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class ParseDiagnostic:
    """One parse-time issue surfaced to the diagnostics layer."""

    env_key: str
    severity: Severity
    message: str
    raw: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedEnvironment:
    """Bundle of parse outcomes + diagnostics from one loader run."""

    outcomes: tuple[ParseOutcome, ...] = field(default_factory=tuple)
    diagnostics: tuple[ParseDiagnostic, ...] = field(default_factory=tuple)
    parsed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
