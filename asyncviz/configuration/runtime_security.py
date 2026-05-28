"""Security-related runtime options.

Today the dashboard runs unauthenticated on loopback. The struct
exists so a future authenticated-dashboard task can flip the
defaults without altering call sites.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.configuration.runtime_defaults import (
    DEFAULT_ALLOW_REMOTE_CONNECTIONS,
    DEFAULT_BIND_LOOPBACK_ONLY,
)


@dataclass(frozen=True, slots=True)
class SecurityOptions:
    """Bind-policy + future-auth knobs."""

    bind_loopback_only: bool = DEFAULT_BIND_LOOPBACK_ONLY
    """Reject ``--host`` values outside loopback unless
    :attr:`allow_remote_connections` is also set."""

    allow_remote_connections: bool = DEFAULT_ALLOW_REMOTE_CONNECTIONS
    """Opt-in to non-loopback binds. Default ``False`` keeps the
    dashboard from accidentally listening on the public network."""
