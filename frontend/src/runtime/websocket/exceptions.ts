/**
 * Typed errors for the websocket client.
 *
 * Kept in their own module so consumers can ``instanceof`` against
 * them without round-tripping through the composed client.
 */

export class WebSocketClientError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WebSocketClientError";
  }
}

export class ProtocolMismatchError extends WebSocketClientError {
  constructor(message: string) {
    super(message);
    this.name = "ProtocolMismatchError";
  }
}

export class HydrationFailedError extends WebSocketClientError {
  constructor(
    message: string,
    public readonly cause?: unknown,
  ) {
    super(message);
    this.name = "HydrationFailedError";
  }
}

export class TransportNotOpenError extends WebSocketClientError {
  constructor(message: string = "transport is not open") {
    super(message);
    this.name = "TransportNotOpenError";
  }
}
