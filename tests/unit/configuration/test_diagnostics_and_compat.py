from __future__ import annotations

from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.configuration import (
    build_configuration_diagnostics,
    clear_configuration_trace,
    from_legacy_config,
    provenance_summary,
    render_diagnostics_lines,
    resolve_options,
    set_configuration_trace_enabled,
    to_legacy_config,
)
from asyncviz.dashboard import create_app


def setup_function(_fn: object) -> None:
    clear_configuration_trace()
    set_configuration_trace_enabled(False)


def test_diagnostics_snapshot_includes_options_and_provenance() -> None:
    resolved = resolve_options(
        profile="dev",
        environ={"ASYNCVIZ_PORT": "9100"},
        cli_overrides={"browser": "never"},
    )
    snap = build_configuration_diagnostics(resolved)
    assert snap.options["network"]["port"] == 9100
    assert "network.port" in snap.provenance
    assert snap.profile_name == "dev"


def test_diagnostics_render_lines_describes_diff() -> None:
    resolved = resolve_options(profile="dev")
    snap = build_configuration_diagnostics(resolved)
    lines = render_diagnostics_lines(snap)
    assert any("profile" in line for line in lines)


def test_provenance_summary_counts_sources() -> None:
    resolved = resolve_options(
        environ={"ASYNCVIZ_PORT": "9100"},
        cli_overrides={"host": "0.0.0.0"},
    )
    summary = provenance_summary(resolved.provenance)
    assert summary.get("DEFAULT", 0) >= 1
    assert summary.get("ENVIRONMENT", 0) >= 1
    assert summary.get("CLI", 0) >= 1


def test_to_legacy_config_preserves_core_fields() -> None:
    resolved = resolve_options(
        environ={"ASYNCVIZ_PORT": "9100"},
        cli_overrides={"host": "0.0.0.0", "browser": "never"},
    )
    legacy = to_legacy_config(resolved.options)
    assert isinstance(legacy, AsyncVizConfig)
    assert legacy.port == 9100
    assert legacy.host == "0.0.0.0"
    assert legacy.open_browser is False


def test_from_legacy_config_round_trips() -> None:
    legacy = AsyncVizConfig(host="0.0.0.0", port=4444, debug=True, open_browser=False)
    options = from_legacy_config(legacy)
    assert options.network.host == "0.0.0.0"
    assert options.network.port == 4444
    assert options.dashboard.debug is True
    assert options.browser.policy == "never"


def test_configuration_endpoint_returns_resolved_options() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/configuration")
    assert response.status_code == 200
    payload = response.json()
    assert "network" in payload["options"]
    assert "provenance" in payload
    assert "diff_from_defaults" in payload
    assert payload["trace_enabled"] is False


def test_configuration_endpoint_appears_in_openapi() -> None:
    app = create_app()
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "/api/configuration" in schema["paths"]
