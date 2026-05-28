"""Module-level ASGI app for external servers (uvicorn, gunicorn, etc.).

Use this entry point when running AsyncViz behind a standalone ASGI server,
e.g. ``uvicorn asyncviz.dashboard.asgi:app --host 0.0.0.0 --port 8877``.

Configuration is read from environment variables via
:meth:`asyncviz.config.AsyncVizConfig.from_env`. The embedded
``asyncviz.start()`` lifecycle does *not* use this module — it builds its
own app internally so it can run uvicorn inside a background thread.
"""

from __future__ import annotations

from fastapi import FastAPI

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app

app: FastAPI = create_app(AsyncVizConfig.from_env())
