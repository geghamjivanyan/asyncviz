"""HTTP surface for the runtime configuration diagnostics.

Exposes ``GET /api/configuration`` so the dashboard's diagnostics
panel + ``asyncviz doctor`` can read the resolved configuration +
provenance without parsing process state.

The endpoint is intentionally cheap — it re-resolves the env layer
on every request so an operator can flip ``ASYNCVIZ_LOG_LEVEL`` in
their shell and immediately see the diff.
"""

from __future__ import annotations

import os
from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.configuration import (
    build_configuration_diagnostics,
    resolve_options,
)

router = APIRouter(tags=["configuration"])


class ConfigurationDiagnosticsResponse(BaseModel):
    """Wire shape for ``GET /api/configuration``."""

    model_config = ConfigDict(frozen=True)

    options: dict = Field(description="Resolved runtime options as a JSON tree.")
    provenance: dict = Field(
        description="Per-option provenance map (`namespace.option` -> {value, source}).",
    )
    profile_name: str | None = Field(default=None)
    diff_from_defaults: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    trace_enabled: bool = False
    trace_count: int = 0


@router.get("/configuration", response_model=ConfigurationDiagnosticsResponse)
async def configuration_diagnostics() -> ConfigurationDiagnosticsResponse:
    """Return the resolved runtime configuration + provenance."""
    resolved = resolve_options(environ=os.environ)
    snapshot = build_configuration_diagnostics(resolved)
    return ConfigurationDiagnosticsResponse(
        options=snapshot.options,
        provenance=snapshot.provenance,
        profile_name=snapshot.profile_name,
        diff_from_defaults={k: list(v) for k, v in snapshot.diff_from_defaults.items()},
        metrics=asdict(snapshot.metrics),
        trace_enabled=snapshot.trace_enabled,
        trace_count=snapshot.trace_count,
    )
