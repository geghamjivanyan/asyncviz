from __future__ import annotations

from collections.abc import Mapping

import pytest

from asyncviz.cli.browser import (
    build_dashboard_url,
    detect_browser_availability,
    should_open_browser,
)


def _env(values: Mapping[str, str]) -> Mapping[str, str]:
    """Convenience: build a mapping that quacks like os.environ.

    The helper exists so tests can assert detection against a known
    environment without polluting the real process env.
    """
    return values


def test_detect_browser_marks_ci_as_unavailable() -> None:
    avail = detect_browser_availability(_env({"CI": "1"}))  # type: ignore[arg-type]
    assert not avail.available
    assert "CI" in avail.reason


def test_detect_browser_respects_asyncviz_no_browser() -> None:
    avail = detect_browser_availability(_env({"ASYNCVIZ_NO_BROWSER": "1"}))  # type: ignore[arg-type]
    assert not avail.available
    assert "ASYNCVIZ_NO_BROWSER" in avail.reason


@pytest.mark.parametrize(
    "preference,available,expected",
    [
        ("always", False, True),
        ("never", True, False),
        ("auto", True, True),
        ("auto", False, False),
    ],
)
def test_should_open_browser_resolves_tri_state(
    preference: str,
    available: bool,
    expected: bool,
) -> None:
    from asyncviz.cli.browser.browser_availability import BrowserAvailability

    decision = should_open_browser(
        preference,  # type: ignore[arg-type]
        BrowserAvailability(
            available=available,
            code="available" if available else "no-display",
            reason="",
        ),
    )
    assert decision is expected


@pytest.mark.parametrize(
    "host,port,expected",
    [
        ("127.0.0.1", 8877, "http://127.0.0.1:8877/"),
        ("0.0.0.0", 8000, "http://127.0.0.1:8000/"),
        ("::1", 9000, "http://[::1]:9000/"),
        ("localhost", 8080, "http://localhost:8080/"),
    ],
)
def test_build_dashboard_url(host: str, port: int, expected: str) -> None:
    assert build_dashboard_url(host=host, port=port) == expected


def test_build_dashboard_url_with_query() -> None:
    url = build_dashboard_url(
        host="127.0.0.1",
        port=8000,
        path="/timeline",
        query={"task": "abc"},
    )
    assert url == "http://127.0.0.1:8000/timeline?task=abc"
