from __future__ import annotations

from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassifier,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagSeverity

from ._helpers import TIGHT_THRESHOLDS, measure


def test_classifier_maps_lag_to_blocking_severity() -> None:
    c = BlockingClassifier()
    cases = [
        (0, BlockingSeverity.NONE, LagSeverity.NORMAL),
        (1_000_000, BlockingSeverity.WARNING, LagSeverity.WARNING),
        (50_000_000, BlockingSeverity.CRITICAL, LagSeverity.CRITICAL),
        (200_000_000, BlockingSeverity.FREEZE, LagSeverity.FREEZE),
    ]
    for lag_ns, expected_severity, expected_source in cases:
        eval_ = TIGHT_THRESHOLDS.evaluate(lag_ns)
        cls = c.classify(measure(lag_ns), eval_)
        assert cls.severity is expected_severity
        assert cls.source_severity is expected_source
        assert cls.lag_ns == lag_ns


def test_classification_is_pure_function() -> None:
    """Same inputs → equal classifications. Replay-safe by construction."""
    c = BlockingClassifier()
    m = measure(5_000_000, index=3)
    eval_ = TIGHT_THRESHOLDS.evaluate(5_000_000)
    a = c.classify(m, eval_)
    b = c.classify(m, eval_)
    assert a == b


def test_is_violation_excludes_none() -> None:
    c = BlockingClassifier()
    none_cls = c.classify(measure(0), TIGHT_THRESHOLDS.evaluate(0))
    warn_cls = c.classify(measure(1_000_000), TIGHT_THRESHOLDS.evaluate(1_000_000))
    assert none_cls.is_violation is False
    assert warn_cls.is_violation is True


def test_severity_ordering() -> None:
    assert (
        BlockingSeverity.NONE
        < BlockingSeverity.WARNING
        < BlockingSeverity.CRITICAL
        < BlockingSeverity.FREEZE
    )
    assert BlockingSeverity.CRITICAL >= BlockingSeverity.WARNING


def test_classification_to_dict_round_trip() -> None:
    c = BlockingClassifier()
    cls = c.classify(measure(50_000_000), TIGHT_THRESHOLDS.evaluate(50_000_000))
    d = cls.to_dict()
    assert d["severity"] == "CRITICAL"
    assert d["lag_ns"] == 50_000_000
    assert d["source_severity"] == "CRITICAL"
