"""Test helpers for the blocking detector.

Currently re-exports the lag monitor's :class:`FakeMonotonicClock` for
deterministic timing tests; future helpers (synthetic measurement
streams, escalation generators) will land here.
"""

from asyncviz.runtime.monitoring.event_loop.utils.fake_clock import FakeMonotonicClock

__all__ = ["FakeMonotonicClock"]
