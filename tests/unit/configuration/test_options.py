from __future__ import annotations

from asyncviz.configuration import (
    BrowserOptions,
    DashboardOptions,
    MonitoringOptions,
    NetworkOptions,
    ReplayOptions,
    RuntimeOptions,
    RuntimeRecordingOptions,
    SecurityOptions,
    WarningOptions,
    default_runtime_options,
)


def test_default_options_assembles_every_domain() -> None:
    options = default_runtime_options()
    assert isinstance(options.network, NetworkOptions)
    assert isinstance(options.dashboard, DashboardOptions)
    assert isinstance(options.browser, BrowserOptions)
    assert isinstance(options.monitoring, MonitoringOptions)
    assert isinstance(options.warning, WarningOptions)
    assert isinstance(options.recording, RuntimeRecordingOptions)
    assert isinstance(options.replay, ReplayOptions)
    assert isinstance(options.security, SecurityOptions)


def test_with_overrides_replaces_named_domains_only() -> None:
    options = default_runtime_options()
    overridden = options.with_overrides(network=NetworkOptions(host="0.0.0.0", port=9000))
    assert overridden.network.host == "0.0.0.0"
    assert overridden.network.port == 9000
    assert overridden.dashboard == options.dashboard


def test_dashboard_url_reflects_network() -> None:
    options = RuntimeOptions(network=NetworkOptions(host="10.0.0.1", port=4242))
    assert options.dashboard_url == "http://10.0.0.1:4242"


def test_dashboard_effective_log_level_follows_debug() -> None:
    options = default_runtime_options().with_overrides(dashboard=DashboardOptions(debug=True))
    assert options.dashboard.effective_log_level == "DEBUG"
    options = default_runtime_options().with_overrides(
        dashboard=DashboardOptions(debug=False),
    )
    assert options.dashboard.effective_log_level == "INFO"


def test_browser_should_attempt_reflects_policy() -> None:
    options = default_runtime_options().with_overrides(browser=BrowserOptions(policy="never"))
    assert options.browser.should_attempt is False
    options = options.with_overrides(browser=BrowserOptions(policy="auto"))
    assert options.browser.should_attempt is True
