"""Network-related runtime options.

Carries the host + port the dashboard binds to plus derived URLs.
Separated from :class:`DashboardOptions` so a future remote-runtime
orchestrator can tweak addresses without dragging dashboard
behavioural knobs along.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.configuration.runtime_defaults import (
    DEFAULT_HOST,
    DEFAULT_PORT,
)


@dataclass(frozen=True, slots=True)
class NetworkOptions:
    """Bind host + port for the embedded dashboard server."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def base_url(self) -> str:
        # 0.0.0.0 isn't browsable — but the URL helper in
        # ``cli.browser`` does the normalization. We keep the
        # base_url honest here so logging shows the actual bind.
        return f"http://{self.host}:{self.port}"
