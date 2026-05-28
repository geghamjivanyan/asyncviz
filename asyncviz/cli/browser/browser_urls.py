"""URL builders for the embedded dashboard.

Lives in its own module so future surfaces (replay deep-links,
inspector-anchored URLs) plug in without touching the launcher.
"""

from __future__ import annotations

from urllib.parse import urlencode


def build_dashboard_url(
    *,
    host: str,
    port: int,
    path: str = "/",
    query: dict[str, str] | None = None,
) -> str:
    """Build a ``http://host:port`` URL with optional path + query."""
    host_part = _format_host(host)
    base = f"http://{host_part}:{port}{path if path.startswith('/') else '/' + path}"
    if not query:
        return base
    return f"{base}?{urlencode(query)}"


def _format_host(host: str) -> str:
    """Normalize the host for URL display.

    * ``0.0.0.0`` becomes ``127.0.0.1`` — a bind-all server isn't
      reachable at the zero address.
    * IPv6 literals get bracketed.
    """
    if host == "0.0.0.0":
        return "127.0.0.1"
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host
