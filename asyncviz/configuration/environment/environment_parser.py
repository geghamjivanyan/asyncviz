"""Typed parsers for env-var values.

Each parser is a pure function from ``str → ParseOutcome``. Parsers
never raise — failures land in the outcome's ``error`` slot. Keeping
parsers exception-free lets the loader walk the registry without a
try/except per entry.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path

from asyncviz.configuration.environment.environment_types import ParseKind, ParseOutcome

Parser = Callable[[str], ParseOutcome]

_TRUTHY = frozenset({"1", "true", "yes", "on", "y", "t"})
_FALSY = frozenset({"0", "false", "no", "off", "n", "f"})

# Duration string: ``250ms`` / ``5s`` / ``1.5m`` / ``0.25h``. Trailing
# unit is mandatory; bare numbers are interpreted via duration_seconds
# / duration_ms parsers below.
_DURATION_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*(ms|s|m|h)\s*$", re.IGNORECASE)
_DURATION_UNIT_TO_SECONDS: dict[str, float] = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
}


def parse_bool(raw: str) -> ParseOutcome:
    """Parse ``raw`` as a boolean. Accepts 1/0/true/false/yes/no/on/off."""
    if raw is None:
        return ParseOutcome.failure(raw="", kind=ParseKind.BOOL, error="missing value")
    normalized = raw.strip().lower()
    if normalized in _TRUTHY:
        return ParseOutcome.success(value=True, raw=raw, kind=ParseKind.BOOL)
    if normalized in _FALSY:
        return ParseOutcome.success(value=False, raw=raw, kind=ParseKind.BOOL)
    return ParseOutcome.failure(
        raw=raw,
        kind=ParseKind.BOOL,
        error=(f"expected one of true/false/yes/no/1/0/on/off, got {raw!r}"),
    )


def parse_int(raw: str) -> ParseOutcome:
    """Parse ``raw`` as a signed integer."""
    try:
        value = int(raw.strip())
    except (ValueError, AttributeError):
        return ParseOutcome.failure(raw=raw, kind=ParseKind.INT, error=f"not an integer: {raw!r}")
    return ParseOutcome.success(value=value, raw=raw, kind=ParseKind.INT)


def parse_float(raw: str) -> ParseOutcome:
    """Parse ``raw`` as a signed float."""
    try:
        value = float(raw.strip())
    except (ValueError, AttributeError):
        return ParseOutcome.failure(raw=raw, kind=ParseKind.FLOAT, error=f"not a number: {raw!r}")
    return ParseOutcome.success(value=value, raw=raw, kind=ParseKind.FLOAT)


def parse_string(raw: str) -> ParseOutcome:
    """Return ``raw`` verbatim — useful for hostnames + log levels."""
    if raw is None or raw.strip() == "":
        return ParseOutcome.failure(raw=raw or "", kind=ParseKind.STRING, error="empty string")
    return ParseOutcome.success(value=raw, raw=raw, kind=ParseKind.STRING)


def parse_duration_seconds(raw: str) -> ParseOutcome:
    """Parse a duration as seconds.

    Accepts ``250ms`` / ``5s`` / ``1.5m`` / bare ``5`` (seconds).
    """
    match = _DURATION_RE.match(raw)
    if match is not None:
        magnitude = float(match.group(1))
        unit = match.group(2).lower()
        return ParseOutcome.success(
            value=magnitude * _DURATION_UNIT_TO_SECONDS[unit],
            raw=raw,
            kind=ParseKind.DURATION_SECONDS,
        )
    bare = parse_float(raw)
    if bare.ok:
        return ParseOutcome.success(
            value=bare.value,
            raw=raw,
            kind=ParseKind.DURATION_SECONDS,
        )
    return ParseOutcome.failure(
        raw=raw,
        kind=ParseKind.DURATION_SECONDS,
        error=f"expected duration (e.g. '250ms', '5s', '1.5m'), got {raw!r}",
    )


def parse_duration_ms(raw: str) -> ParseOutcome:
    """Parse a duration as milliseconds."""
    outcome = parse_duration_seconds(raw)
    if not outcome.ok:
        return ParseOutcome.failure(
            raw=raw,
            kind=ParseKind.DURATION_MS,
            error=outcome.error or "invalid",
        )
    return ParseOutcome.success(
        value=outcome.value * 1000.0,
        raw=raw,
        kind=ParseKind.DURATION_MS,
    )


def parse_path(raw: str) -> ParseOutcome:
    """Parse a filesystem path (expanding ``~`` + env vars)."""
    if raw is None or raw.strip() == "":
        return ParseOutcome.failure(raw=raw or "", kind=ParseKind.PATH, error="empty path")
    import os as _os

    expanded = _os.path.expanduser(_os.path.expandvars(raw))
    return ParseOutcome.success(value=Path(expanded), raw=raw, kind=ParseKind.PATH)


def parse_enum(*, choices: Sequence[str]) -> Parser:
    """Build a parser that accepts only one of ``choices``.

    Matching is case-insensitive but the *returned* value preserves
    the casing from ``choices`` — that's what downstream consumers
    use for ``Literal[...]`` comparison.
    """
    by_lower = {c.lower(): c for c in choices}

    def _parse(raw: str) -> ParseOutcome:
        if raw is None:
            return ParseOutcome.failure(raw="", kind=ParseKind.ENUM, error="missing value")
        candidate = raw.strip().lower()
        canonical = by_lower.get(candidate)
        if canonical is None:
            return ParseOutcome.failure(
                raw=raw,
                kind=ParseKind.ENUM,
                error=f"expected one of {list(by_lower.values())}, got {raw!r}",
            )
        return ParseOutcome.success(value=canonical, raw=raw, kind=ParseKind.ENUM)

    return _parse


def parse_list(*, separator: str = ",") -> Parser:
    """Build a parser that splits ``raw`` on ``separator`` into a tuple."""

    def _parse(raw: str) -> ParseOutcome:
        if raw is None or raw.strip() == "":
            return ParseOutcome.success(value=(), raw=raw or "", kind=ParseKind.LIST)
        parts = tuple(p.strip() for p in raw.split(separator) if p.strip())
        return ParseOutcome.success(value=parts, raw=raw, kind=ParseKind.LIST)

    return _parse


# Convenience registry consumed by the loader so it doesn't have to
# know about every parser name.
PARSER_REGISTRY: dict[ParseKind, Parser] = {
    ParseKind.BOOL: parse_bool,
    ParseKind.INT: parse_int,
    ParseKind.FLOAT: parse_float,
    ParseKind.STRING: parse_string,
    ParseKind.DURATION_SECONDS: parse_duration_seconds,
    ParseKind.DURATION_MS: parse_duration_ms,
    ParseKind.PATH: parse_path,
}
