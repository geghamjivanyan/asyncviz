/**
 * Websocket URL builder.
 *
 * Composes the base URL with the optional ``since_sequence`` cursor.
 * Centralized so the URL shape is one source of truth — any future
 * query parameter (auth token, subscription topics) lands here.
 */

export interface WebSocketUrlOptions {
  /** Replay cursor — set on reconnect so the server streams the gap. */
  sinceSequence?: number;
}

export function buildWebSocketUrl(base: string, options: WebSocketUrlOptions = {}): string {
  const { sinceSequence } = options;
  if (sinceSequence === undefined || !Number.isFinite(sinceSequence) || sinceSequence <= 0) {
    return base;
  }
  const separator = base.includes("?") ? "&" : "?";
  return `${base}${separator}since_sequence=${Math.trunc(sinceSequence)}`;
}
