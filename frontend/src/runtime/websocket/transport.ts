/**
 * Pluggable websocket transport.
 *
 * The :class:`RuntimeWebSocketClient` does not talk to ``WebSocket``
 * directly — it talks to the :interface:`WebSocketTransport`
 * abstraction. Two implementations ship today:
 *
 *   * :class:`NativeWebSocketTransport` wraps the browser ``WebSocket``
 *     for production use.
 *   * Tests build their own fake transport (the contract is small —
 *     ``open``, ``close``, ``send`` + four event handlers).
 *
 * Keeping the transport pluggable means JSDOM tests can drive the
 * full reconnect / replay / hydration paths without an actual
 * websocket connection.
 */

export type TransportEvent =
  | { kind: "open" }
  | { kind: "close"; code: number; reason: string; wasClean: boolean }
  | { kind: "error"; message: string }
  | { kind: "message"; data: string };

export type TransportEventListener = (event: TransportEvent) => void;

export type TransportReadyState = "idle" | "opening" | "open" | "closing" | "closed";

export interface WebSocketTransport {
  readonly url: string;
  readonly readyState: TransportReadyState;
  open(): void;
  close(code?: number, reason?: string): void;
  send(payload: string): void;
  setListener(listener: TransportEventListener | null): void;
}

/**
 * Production transport — thin shim over the browser ``WebSocket``.
 *
 * Re-creating the underlying ``WebSocket`` per :meth:`open` call is
 * intentional: the native ``WebSocket`` is not reusable after a close.
 * The wrapping object stays stable so the client can hold a reference
 * across reconnects.
 */
export class NativeWebSocketTransport implements WebSocketTransport {
  private _socket: WebSocket | null = null;
  private _listener: TransportEventListener | null = null;
  private _readyState: TransportReadyState = "idle";

  constructor(public readonly url: string) {}

  get readyState(): TransportReadyState {
    return this._readyState;
  }

  setListener(listener: TransportEventListener | null): void {
    this._listener = listener;
  }

  open(): void {
    if (this._socket !== null) return;
    this._readyState = "opening";
    const socket = new WebSocket(this.url);
    this._socket = socket;
    socket.addEventListener("open", () => {
      this._readyState = "open";
      this._listener?.({ kind: "open" });
    });
    socket.addEventListener("message", (event: MessageEvent<string>) => {
      this._listener?.({ kind: "message", data: event.data });
    });
    socket.addEventListener("error", () => {
      this._listener?.({ kind: "error", message: "websocket error" });
    });
    socket.addEventListener("close", (event: CloseEvent) => {
      this._socket = null;
      this._readyState = "closed";
      this._listener?.({
        kind: "close",
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
      });
    });
  }

  close(code?: number, reason?: string): void {
    if (this._socket === null) return;
    this._readyState = "closing";
    this._socket.close(code, reason);
  }

  send(payload: string): void {
    this._socket?.send(payload);
  }
}
