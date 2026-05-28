from __future__ import annotations


class GatewayError(Exception):
    """Base class for every :class:`WebSocketGateway` failure."""


class HandshakeError(GatewayError):
    """Raised when the websocket handshake (replay request, session setup) fails.

    Surfaced to the client as a ``protocol_error`` envelope before the
    connection is closed.
    """


class ReplayWindowExhaustedError(HandshakeError):
    """Replay was requested but retention has rolled past the asked sequence."""


class SlowClientError(GatewayError):
    """Raised when a session's outbound queue blows past its bounded capacity.

    The gateway disconnects the offending client rather than block the
    broadcast pipeline.
    """


class UnknownSessionError(GatewayError):
    """Raised by strict reads against a non-existent ``session_id``."""
