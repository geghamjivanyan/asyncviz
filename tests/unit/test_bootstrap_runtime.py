from __future__ import annotations

import asyncviz
from asyncviz.bootstrap import AsyncVizRuntime, bootstrap as bootstrap_module


def test_get_runtime_returns_none_when_idle() -> None:
    assert asyncviz.get_runtime() is None
    assert asyncviz.is_running() is False


def test_bootstrap_state_is_module_singleton() -> None:
    state_a = bootstrap_module._state
    state_b = bootstrap_module._state
    assert state_a is state_b
    assert isinstance(state_a, bootstrap_module._BootstrapState)


def test_runtime_dataclass_exposes_documented_properties() -> None:
    fields = {f.name for f in AsyncVizRuntime.__dataclass_fields__.values()}
    assert {"config", "services", "started_at", "server", "thread"} <= fields
    assert "dashboard_url" in AsyncVizRuntime.__dict__
    assert "is_running" in AsyncVizRuntime.__dict__
    assert "shutdown" in AsyncVizRuntime.__dict__
