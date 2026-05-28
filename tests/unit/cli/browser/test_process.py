from __future__ import annotations

import webbrowser

import pytest

from asyncviz.cli.browser.browser_process import (
    NoopBackend,
    StubBackend,
    WebbrowserBackend,
)


def test_stub_backend_records_calls() -> None:
    backend = StubBackend(succeed=True)
    outcome = backend.open("http://x/")
    assert outcome.success
    assert outcome.backend == "stub"
    assert backend.calls == ["http://x/"]


def test_stub_backend_can_simulate_failure() -> None:
    backend = StubBackend(succeed=False)
    assert not backend.open("http://x/").success


def test_noop_backend_never_opens() -> None:
    backend = NoopBackend()
    outcome = backend.open("http://x/")
    assert not outcome.success
    assert outcome.backend == "noop"


def test_webbrowser_backend_handles_browser_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise webbrowser.Error("no browser")

    monkeypatch.setattr(webbrowser, "open", boom)
    outcome = WebbrowserBackend().open("http://x/")
    assert not outcome.success
    assert "no browser" in outcome.detail


def test_webbrowser_backend_handles_open_returning_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(webbrowser, "open", lambda *a, **kw: False)
    outcome = WebbrowserBackend().open("http://x/")
    assert not outcome.success
    assert "returned False" in outcome.detail
