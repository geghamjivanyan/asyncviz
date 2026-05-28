from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asyncviz.runtime.events import EventBus, RuntimeEvent


def test_event_bus_starts_with_dashboard_lifespan(app: FastAPI) -> None:
    bus: EventBus = app.state.event_bus
    received: list[RuntimeEvent] = []
    bus.subscribe(received.append, event_types={"smoke"})

    with TestClient(app) as client:
        assert bus.is_running
        # Sanity: API still works while the bus is up.
        assert client.get("/api/health").status_code == 200
        bus.publish(RuntimeEvent.of("smoke", source="lifespan"))

        # Let the dispatcher drain. TestClient runs lifespan on a thread of
        # its own; we can't await bus.join() from this sync test, so loop
        # until the metric updates.
        import time

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not received:
            time.sleep(0.01)
        assert received and received[0].event_type == "smoke"

    # Lifespan exit should have stopped the bus.
    assert bus.is_running is False


def test_event_bus_is_per_app_instance() -> None:
    from asyncviz.config import AsyncVizConfig
    from asyncviz.dashboard import create_app

    a = create_app(AsyncVizConfig(open_browser=False, heartbeat_interval=60.0))
    b = create_app(AsyncVizConfig(open_browser=False, heartbeat_interval=60.0))
    assert a.state.event_bus is not b.state.event_bus
