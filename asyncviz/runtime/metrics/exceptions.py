from __future__ import annotations


class MetricsError(Exception):
    """Base class for every :class:`RuntimeMetricsAggregator` failure."""


class MetricsRebuildError(MetricsError):
    """Raised when :meth:`RuntimeMetricsAggregator.rebuild` finds inconsistent input."""


class MetricsSubscriptionError(MetricsError):
    """Raised when subscription / unsubscription is misused."""
