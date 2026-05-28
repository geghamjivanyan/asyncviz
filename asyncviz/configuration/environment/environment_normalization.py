"""Cross-platform key normalization for env-var lookups.

Windows env vars are case-insensitive; POSIX env vars are
case-sensitive. The loader keeps lookups deterministic by always
uppercasing the key + collapsing runs of separator characters.
"""

from __future__ import annotations

import re

_SEPARATOR_RE = re.compile(r"[-.\s]+")


def normalize_env_key(key: str, *, namespace: str | None = None) -> str:
    """Return the canonical env-var name for ``key``.

    * uppercased,
    * dots / dashes / whitespace collapsed to underscores,
    * leading namespace prepended when supplied (and not already
      present).
    """
    if not key:
        return key
    normalized = _SEPARATOR_RE.sub("_", key.strip()).upper()
    if namespace and not normalized.startswith(namespace.upper()):
        normalized = f"{namespace}{normalized}".upper()
    return normalized


def strip_namespace(key: str, namespace: str) -> str:
    """Return ``key`` with ``namespace`` removed from the front."""
    up = key.upper()
    ns = namespace.upper()
    return up[len(ns):] if up.startswith(ns) else up
