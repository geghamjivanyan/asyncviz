from __future__ import annotations

import pytest

from asyncviz.bootstrap import browser as browser_module


def test_open_browser_safely_invokes_webbrowser_in_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []
    monkeypatch.setattr(browser_module.webbrowser, "open", called.append)

    thread = browser_module.open_browser_safely("http://127.0.0.1:8877", delay=0.0)
    thread.join(timeout=2.0)

    assert called == ["http://127.0.0.1:8877"]


def test_open_browser_safely_swallows_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_url: str) -> bool:
        raise browser_module.webbrowser.Error("no browser")

    monkeypatch.setattr(browser_module.webbrowser, "open", boom)
    thread = browser_module.open_browser_safely("http://127.0.0.1:8877", delay=0.0)
    thread.join(timeout=2.0)
    # No exception escaped; we exited cleanly.
