"""Canonical cache-control policies for the frontend-serving layer.

Three categories, three policies:

* **Immutable** — Vite content-hashed assets in ``/assets/``. Any
  change produces a fresh filename, so we can pin them for a year.
* **Short** — Loose assets that share a stable URL (``favicon.ico``,
  ``manifest.webmanifest``, ``robots.txt``). One-hour cache balances
  rotation against refresh storms.
* **No-store** — ``index.html`` itself. It points at the hashed JS/CSS
  bundles, so revalidating it every load is the only way a deployed
  bundle change ever reaches a returning user.
"""

from __future__ import annotations

from enum import StrEnum

#: One-year immutable cache for hashed assets.
CACHE_IMMUTABLE = "public, max-age=31536000, immutable"

#: One-hour cache for loose assets with stable URLs.
CACHE_SHORT = "public, max-age=3600"

#: Revalidate every request — used for ``index.html``.
CACHE_NO_CACHE = "no-cache"


class CachePolicy(StrEnum):
    """The categories the service distinguishes between."""

    IMMUTABLE = "immutable"
    SHORT = "short"
    NO_CACHE = "no-cache"


def header_for(policy: CachePolicy) -> str:
    """Return the wire ``Cache-Control`` value for ``policy``."""
    return _POLICY_HEADERS[policy]


_POLICY_HEADERS: dict[CachePolicy, str] = {
    CachePolicy.IMMUTABLE: CACHE_IMMUTABLE,
    CachePolicy.SHORT: CACHE_SHORT,
    CachePolicy.NO_CACHE: CACHE_NO_CACHE,
}
