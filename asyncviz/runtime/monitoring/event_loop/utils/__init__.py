"""Test + integration helpers for the lag monitor.

Production code does not depend on this module. The fake clock here is
the canonical deterministic time source used by every lag-monitor test.
"""

from asyncviz.runtime.monitoring.event_loop.utils.fake_clock import FakeMonotonicClock

__all__ = ["FakeMonotonicClock"]
