from __future__ import annotations

import socket
import urllib.error
import urllib.request
from contextlib import closing

import pytest

import asyncviz
from asyncviz.bootstrap import (
    AsyncVizRuntime,
    PortInUseError,
    StartupTimeoutError,
    bootstrap as bootstrap_module,
)


def _reserve_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.integration
def test_start_returns_runtime_and_is_idempotent() -> None:
    port = _reserve_port()
    runtime = asyncviz.start(host="127.0.0.1", port=port, open_browser=False)
    try:
        assert isinstance(runtime, AsyncVizRuntime)
        assert runtime.is_running
        assert runtime.dashboard_url == f"http://127.0.0.1:{port}"
        assert asyncviz.is_running()
        assert asyncviz.get_runtime() is runtime

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            assert response.status == 200

        # Second start should be a no-op and return the same runtime.
        again = asyncviz.start(host="127.0.0.1", port=port, open_browser=False)
        assert again is runtime
    finally:
        asyncviz.stop()

    assert asyncviz.is_running() is False
    assert asyncviz.get_runtime() is None

    # Calling stop() repeatedly must be safe.
    asyncviz.stop()
    asyncviz.stop()

    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)


@pytest.mark.integration
def test_start_raises_port_in_use() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        with pytest.raises(PortInUseError):
            asyncviz.start(host="127.0.0.1", port=port, open_browser=False)
    finally:
        sock.close()


@pytest.mark.integration
def test_start_raises_startup_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bootstrap_module,
        "_wait_until_ready",
        lambda *_args, **_kwargs: False,
    )

    port = _reserve_port()
    with pytest.raises(StartupTimeoutError):
        asyncviz.start(host="127.0.0.1", port=port, open_browser=False, startup_timeout=0.1)
    assert asyncviz.is_running() is False
