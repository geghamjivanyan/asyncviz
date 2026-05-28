"""Dashboard-facing replay integration.

Bridges :mod:`asyncviz.replay.runtime` (the playback engine) to the
dashboard's existing websocket fan-out so the SPA can render
recorded sessions through the same realtime pipeline it uses for
live runs.
"""

from asyncviz.dashboard.replay.dashboard_sink import DashboardReplaySink

__all__ = ["DashboardReplaySink"]
