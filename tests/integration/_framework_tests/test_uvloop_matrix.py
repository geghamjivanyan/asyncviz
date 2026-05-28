"""uvloop matrix tests — skipped when uvloop isn't installed."""

from __future__ import annotations

import pytest

from asyncviz.runtime.compat import (  # type: ignore[import-not-found]
    is_uvloop_available,
)
from tests.integration._framework import (
    IntegrationRunInputs,
    IntegrationRunner,
    default_config,
)

pytestmark = pytest.mark.skipif(
    not is_uvloop_available(),
    reason="uvloop not installed",
)


async def test_replay_determinism_matches_under_uvloop() -> None:
    cfg = default_config()
    runner = IntegrationRunner(config=cfg)
    outcomes = await runner.run(
        IntegrationRunInputs(
            only=("replay.determinism",),
            determinism=True,
            uvloop_matrix=True,
        ),
    )
    outcome = outcomes[0]
    assert outcome.uvloop_matrix_run is True
    assert outcome.uvloop_diverged is False
    assert outcome.verdict == "passed"


async def test_topology_pipeline_matches_under_uvloop() -> None:
    cfg = default_config()
    runner = IntegrationRunner(config=cfg)
    outcomes = await runner.run(
        IntegrationRunInputs(
            only=("topology.topology_pipeline",),
            uvloop_matrix=True,
        ),
    )
    outcome = outcomes[0]
    assert outcome.uvloop_matrix_run is True
    assert outcome.uvloop_diverged is False
