from __future__ import annotations

import socket
from contextlib import closing
from pathlib import Path

import pytest

from asyncviz.bootstrap.validation import (
    ConfigError,
    PortInUseError,
    check_frontend_mode,
    check_port_available,
)
from asyncviz.config import AsyncVizConfig


def test_check_frontend_mode_auto_is_permissive(tmp_path: Path) -> None:
    check_frontend_mode(AsyncVizConfig(frontend_mode="auto"), tmp_path)


def test_check_frontend_mode_api_only_skips_check(tmp_path: Path) -> None:
    check_frontend_mode(AsyncVizConfig(frontend_mode="api-only"), tmp_path)


def test_check_frontend_mode_embedded_requires_index_html(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        check_frontend_mode(AsyncVizConfig(frontend_mode="embedded"), tmp_path)


def test_check_frontend_mode_embedded_passes_when_index_present(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html></html>")
    check_frontend_mode(AsyncVizConfig(frontend_mode="embedded"), tmp_path)


def test_check_port_available_passes_for_free_port() -> None:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    check_port_available("127.0.0.1", free_port)


def test_check_port_available_raises_for_taken_port() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        with pytest.raises(PortInUseError):
            check_port_available("127.0.0.1", port)
    finally:
        sock.close()
