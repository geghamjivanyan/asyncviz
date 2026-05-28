"""Backend middleware layer.

* :class:`CorrelationIdMiddleware` — stamps every request with a stable id.
* :class:`RequestTimingMiddleware` — measures + records duration.
* :class:`RequestLoggingMiddleware` — emits one structured log line per
  request.
* :class:`ErrorNormalizationMiddleware` — catches unhandled exceptions
  and turns them into canonical JSON envelopes.

Order matters. Apply in this sequence on the FastAPI app::

    app.add_middleware(ErrorNormalizationMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

Starlette executes middleware in reverse-added order on the request side
and in added order on the response side. With the order above, the
correlation id is set first (so timing + logging can reference it) and
errors are normalized last (the outermost layer the client sees).
"""

from asyncviz.dashboard.middleware.correlation import (
    CORRELATION_HEADER,
    CorrelationIdMiddleware,
    current_correlation_id,
)
from asyncviz.dashboard.middleware.errors import ErrorNormalizationMiddleware
from asyncviz.dashboard.middleware.logging import RequestLoggingMiddleware
from asyncviz.dashboard.middleware.timing import (
    TIMING_HEADER,
    RequestTimingMiddleware,
)

__all__ = [
    "CORRELATION_HEADER",
    "TIMING_HEADER",
    "CorrelationIdMiddleware",
    "ErrorNormalizationMiddleware",
    "RequestLoggingMiddleware",
    "RequestTimingMiddleware",
    "current_correlation_id",
]
