"""SPA routing predicate.

A single source of truth for "should this URL fall through to the SPA
catch-all?". Keeping the rule in one place means the catch-all handler,
the diagnostics endpoint, and any future router consumer agree on what
is "frontend" vs. "backend" without copy-pasting prefixes.

Routing contract
----------------
Backend / system routes ("reserved" prefixes below) must NEVER resolve
to ``index.html``. Everything else may fall through to the SPA so React
Router can deep-link.

Reserved prefixes are stored in the canonical leading-slash form so the
list reads the same way operators write it in URLs and configuration.
The matcher normalizes incoming paths (FastAPI's ``{full_path:path}``
strips the leading slash) so both ``"health"`` and ``"/health"`` resolve
the same way.

Prefix matching uses **path-segment boundaries**: ``/api`` matches
``/api`` and ``/api/<anything>`` but not ``/api-docs`` (which is its own
top-level route, not a child of ``/api``). This avoids the classic
``startswith`` foot-gun where ``"/api"`` would silently swallow
``"/apiary"``.
"""

from __future__ import annotations

#: Backend / system route prefixes that must bypass the SPA fallback.
#:
#: Canonical form is leading-slash so the list is identical to what an
#: operator types into a browser or a curl command. Matching is done
#: through :func:`is_reserved_path`, which handles the
#: catch-all's no-leading-slash form transparently.
#:
#: Add new backend mounts here (and only here) when introducing new
#: top-level system routes. The diagnostics endpoint, the SPA
#: catch-all, and any future static-fallback consumer all read from
#: this one tuple.
RESERVED_PREFIXES: tuple[str, ...] = (
    "/api",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/ws",
)


def _canonicalize(path: str) -> str:
    """Return ``path`` with exactly one leading ``/``.

    FastAPI's ``{full_path:path}`` matcher strips the leading slash
    (e.g. ``/health/live`` arrives as ``"health/live"``), while ASGI
    ``scope["path"]`` keeps it. Both forms must produce the same
    verdict, so normalize before comparing.
    """
    return "/" + path.lstrip("/")


def is_reserved_path(path: str) -> bool:
    """Return ``True`` when ``path`` belongs to a backend / system route.

    Accepts either the catch-all form (``"health/live"``) or the raw
    request form (``"/health/live"``). Matching respects path-segment
    boundaries: ``/api`` matches ``/api`` and ``/api/...`` but not
    ``/api-docs``.

    Used by the SPA catch-all to decide between a 404 (reserved backend
    route the SPA must not shadow) and an ``index.html`` fallback
    (genuine SPA deep-link).
    """
    normalized = _canonicalize(path)
    for prefix in RESERVED_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False
