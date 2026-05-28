from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.event_loop.lag_configuration import (
    DEFAULT_SAMPLE_INTERVAL_SECONDS,
    LagConfiguration,
)
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagThresholds


def test_default_configuration_has_sensible_values() -> None:
    c = LagConfiguration.default()
    assert c.sample_interval_seconds == DEFAULT_SAMPLE_INTERVAL_SECONDS
    assert c.statistics_window > 0
    assert c.emit_threshold_breach_events is True
    assert c.emit_measurement_events is False


def test_with_interval_returns_new_instance() -> None:
    c = LagConfiguration.default()
    c2 = c.with_interval(0.01)
    assert c is not c2
    assert c2.sample_interval_seconds == 0.01
    assert c.sample_interval_seconds == DEFAULT_SAMPLE_INTERVAL_SECONDS


def test_with_thresholds_replaces_thresholds() -> None:
    c = LagConfiguration.default()
    new_thresholds = LagThresholds(warning_seconds=0.001)
    c2 = c.with_thresholds(new_thresholds)
    assert c2.thresholds is new_thresholds
    assert c.thresholds is not new_thresholds


def test_invalid_interval_raises() -> None:
    with pytest.raises(ValueError, match="sample_interval_seconds must be > 0"):
        LagConfiguration(sample_interval_seconds=0)
    with pytest.raises(ValueError, match="sample_interval_seconds must be > 0"):
        LagConfiguration(sample_interval_seconds=-1)


def test_invalid_window_raises() -> None:
    with pytest.raises(ValueError, match="statistics_window must be > 0"):
        LagConfiguration(statistics_window=0)


def test_to_dict_carries_canonical_fields() -> None:
    c = LagConfiguration.default()
    d = c.to_dict()
    assert d["sample_interval_seconds"] == c.sample_interval_seconds
    assert "thresholds" in d
    assert "statistics_window" in d
    assert d["emit_threshold_breach_events"] is True
