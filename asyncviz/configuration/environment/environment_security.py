"""Secret-aware redaction for env-var diagnostics.

The loader marks specific :class:`EnvVarSpec` entries with
``secret=True`` so their values never reach the diagnostics surface.
For *unknown* env vars we still want to be conservative: this module
exposes a heuristic that classifies arbitrary keys as sensitive
based on a small suffix table.
"""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.configuration.environment.environment_defaults import SECRET_KEY_SUFFIXES

#: Sentinel string used in place of redacted values.
REDACTED_VALUE = "<redacted>"


def is_secret_key(key: str, *, suffixes: Iterable[str] = SECRET_KEY_SUFFIXES) -> bool:
    """Return True when ``key`` looks like it carries a secret."""
    if not key:
        return False
    upper = key.upper()
    return any(upper.endswith(suffix) for suffix in suffixes)


def redact_value(key: str, value: str) -> str:
    """Return ``REDACTED_VALUE`` when ``key`` looks sensitive; ``value`` otherwise."""
    return REDACTED_VALUE if is_secret_key(key) else value


def redact_mapping(values: dict[str, str]) -> dict[str, str]:
    """Apply :func:`redact_value` to every entry in ``values``."""
    return {k: redact_value(k, v) for k, v in values.items()}
