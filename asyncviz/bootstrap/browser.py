from __future__ import annotations

import threading
import time
import webbrowser

from asyncviz.utils.logging import get_logger

logger = get_logger("bootstrap.browser")

_OPEN_DELAY_SECONDS = 0.2


def open_browser_safely(url: str, *, delay: float = _OPEN_DELAY_SECONDS) -> threading.Thread:
    """Open ``url`` in the user's browser without blocking.

    The actual ``webbrowser.open`` call happens in a daemon thread after a
    short delay so uvicorn has settled. Any failure is logged at DEBUG and
    never propagates to the caller — opening a browser is best-effort.
    """

    def _open() -> None:
        try:
            if delay > 0:
                time.sleep(delay)
            opened = webbrowser.open(url)
            if not opened:
                logger.debug("webbrowser.open(%r) returned False", url)
        except webbrowser.Error as exc:
            logger.debug("Could not open browser: %s", exc)
        except Exception as exc:
            logger.debug("Unexpected browser-open failure: %s", exc)

    thread = threading.Thread(target=_open, name="asyncviz-browser", daemon=True)
    thread.start()
    return thread
