"""Canonical JSON encoding used across the replay format.

Why a separate module: ``json.dumps(sort_keys=True)`` is *almost*
canonical but leaves three nondeterminisms in place that bite replay
systems:

1. Whitespace around separators (``": "`` vs ``":"``).
2. Float repr varies between Python versions for edge values like
   ``inf`` / ``nan``.
3. Nested mappings under non-canonical key ordering when the caller
   bypassed ``sort_keys`` (e.g. via custom encoders).

The helpers here normalize all three. The encoded bytes are stable
across runs, machines, and Python patch releases — which is the
property hashing + cross-version replay both depend on.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

_SEPARATORS = (",", ":")


class CanonicalEncodingError(ValueError):
    """Raised when a value cannot be encoded deterministically."""


def _check_finite(obj: Any) -> Any:
    """Float guard — :data:`nan` / :data:`inf` are not valid JSON and
    silently round-tripping them through Python's encoder produces
    non-canonical strings that other JSON readers reject."""
    if isinstance(obj, float) and not math.isfinite(obj):
        raise CanonicalEncodingError(f"non-finite float in payload: {obj!r}")
    return obj


def sort_mapping(value: Any) -> Any:
    """Recursively sort dict keys so that *nested* dicts also encode
    deterministically. ``json.dumps(sort_keys=True)`` only sorts at
    each level; this normalization makes the input itself canonical
    so hashing the *Python* object also yields a stable digest."""
    if isinstance(value, Mapping):
        return {k: sort_mapping(value[k]) for k in sorted(value)}
    if isinstance(value, list | tuple):
        # Lists are sequences — order is semantic, do not sort.
        return [sort_mapping(v) for v in value]
    return _check_finite(value)


def canonical_dumps(value: Any) -> str:
    """Encode ``value`` to a stable JSON string.

    Properties:
    * keys sorted at every nesting level
    * no whitespace
    * UTF-8 round-trip safe (``ensure_ascii=False``)
    * :data:`nan` / :data:`inf` rejected loudly rather than silently
      written as the non-JSON tokens ``NaN`` / ``Infinity``
    """
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=_SEPARATORS,
            allow_nan=False,
        )
    except ValueError as exc:
        # json.dumps raises plain ValueError for non-finite floats
        # when allow_nan=False; wrap so callers can catch one type.
        raise CanonicalEncodingError(str(exc)) from exc


def canonical_loads(payload: str | bytes) -> Any:
    """Parse a JSON string. Wrapper for symmetry with
    :func:`canonical_dumps`; centralizes the call site so future
    codec swaps (orjson, msgpack) land in one place."""
    return json.loads(payload)
