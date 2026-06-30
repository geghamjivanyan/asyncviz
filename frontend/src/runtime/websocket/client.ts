/**
 * Canonical runtime websocket client.
 *
 * Composes every websocket primitive into a single high-level client:
 *
 *   * :class:`WebSocketTransport` — wire layer (pluggable for tests).
 *   * :class:`SequenceTracker` — duplicate / stale / out-of-order
 *     reconciliation.
 *   * :class:`ReconnectScheduler` — exponential backoff with jitter.
 *   * :class:`HeartbeatMonitor` — stale-connection detection.
 *   * :class:`SubscriptionRegistry` — typed envelope fanout.
 *   * :func:`fetchSnapshot` — hydration orchestrator.
 *   * :class:`WebSocketDiagnostics` — debug ring (off by default).
 *
 * Public API:
 *
 *   ``start()``      — kicks off hydration + websocket open.
 *   ``stop()``       — graceful shutdown.
 *   ``forceReconnect()`` — used by tests + future "reload" UX.
 *   ``subscribe(filter, listener)`` — typed envelope subscription.
 *   ``getPhase()``   — current :class:`ConnectionPhase`.
 *   ``getSequence()``— last sequence the client accepted.
 */

import type { ConnectionState, RuntimeEnvelope } from "@/types/runtime";
import { HeartbeatMonitor, type HeartbeatOptions } from "@/runtime/websocket/heartbeat";
import { HydrationFailedError, WebSocketClientError } from "@/runtime/websocket/exceptions";
import { fetchSnapshot, type HydrationResult } from "@/runtime/websocket/hydration";
import {
  isTerminalPhase,
  toConnectionState,
  type ConnectionPhase,
} from "@/runtime/websocket/lifecycle";
import {
  parseEnvelope,
  type ParseOutcome,
  type ProtocolOptions,
} from "@/runtime/websocket/protocol";
import { ReconnectScheduler, type ReconnectOptions } from "@/runtime/websocket/reconnect";
import { SequenceTracker } from "@/runtime/websocket/sequencing";
import {
  SubscriptionRegistry,
  type EnvelopeListener,
  type Subscription,
  type SubscriptionFilter,
} from "@/runtime/websocket/subscriptions";
import { buildWebSocketUrl } from "@/runtime/websocket/url";
import type { TransportEvent, WebSocketTransport } from "@/runtime/websocket/transport";
import { WebSocketDiagnostics, type DiagnosticsOptions } from "@/runtime/websocket/diagnostics";

export type RejectReason =
  "invalid-json" | "invalid-shape" | "unknown-type" | "protocol-mismatch" | "duplicate" | "stale";

export interface RuntimeWebSocketClientOptions {
  /** Pre-built transport. Production builds inject :class:`NativeWebSocketTransport`. */
  transport: WebSocketTransport;
  /** Pluggable fetcher for hydration; defaults to ``fetch``. */
  fetcher?: typeof fetch;
  /** REST origin for ``/api/runtime/snapshot``. */
  apiBaseUrl: string;
  /** Protocol version the client speaks. Must match the backend. */
  protocolVersion: string;
  /** When ``true`` skip the protocol-version check; tests + dev only. */
  allowAnyProtocolVersion?: boolean;
  /** Reconnect schedule overrides. */
  reconnect?: ReconnectOptions;
  /** Heartbeat overrides. */
  heartbeat?: HeartbeatOptions;
  /** Diagnostics overrides. */
  diagnostics?: DiagnosticsOptions;
  /** Hook fired on every phase transition. */
  onPhaseChange?: (phase: ConnectionPhase) => void;
  /** Hook fired with the projected legacy :type:`ConnectionState`. */
  onConnectionStateChange?: (state: ConnectionState) => void;
  /** Hook fired with the snapshot payload after a successful hydration. */
  onHydrated?: (result: HydrationResult) => void;
  /** Hook fired on every envelope that was accepted (post-reconciliation). */
  onEnvelope?: (envelope: RuntimeEnvelope) => void;
  /** Hook fired with structured rejection metadata; powers metrics. */
  onReject?: (reason: RejectReason, detail?: string) => void;
  /** Hook fired when a recoverable error occurs. */
  onError?: (error: WebSocketClientError) => void;
  /** Optional setTimeout override — tests use ``vi.useFakeTimers``. */
  setTimer?: (callback: () => void, ms: number) => unknown;
  clearTimer?: (id: unknown) => void;
}

/**
 * Transports may expose ``setUrl`` so the client can swap the cursor
 * (``?since_sequence=N``) on reconnect. Production
 * :class:`NativeWebSocketTransport` doesn't (URLs are baked at
 * construction); a wrapper transport that supports it can implement
 * this interface and the client will use the runtime hook.
 */
interface UrlAwareTransport extends WebSocketTransport {
  setUrl(url: string): void;
}

function isUrlAwareTransport(t: WebSocketTransport): t is UrlAwareTransport {
  return typeof (t as { setUrl?: unknown }).setUrl === "function";
}

export class RuntimeWebSocketClient {
  private readonly _transport: WebSocketTransport;
  private readonly _fetcher: typeof fetch;
  private readonly _apiBaseUrl: string;
  private readonly _protocol: ProtocolOptions;
  private readonly _reconnect: ReconnectScheduler;
  private readonly _heartbeat: HeartbeatMonitor;
  private readonly _diagnostics: WebSocketDiagnostics;
  private readonly _subscriptions = new SubscriptionRegistry();
  private readonly _sequence = new SequenceTracker();
  private readonly _setTimer: (callback: () => void, ms: number) => unknown;
  private readonly _clearTimer: (id: unknown) => void;
  private readonly _hooks: {
    phase?: RuntimeWebSocketClientOptions["onPhaseChange"];
    connectionState?: RuntimeWebSocketClientOptions["onConnectionStateChange"];
    hydrated?: RuntimeWebSocketClientOptions["onHydrated"];
    envelope?: RuntimeWebSocketClientOptions["onEnvelope"];
    reject?: RuntimeWebSocketClientOptions["onReject"];
    error?: RuntimeWebSocketClientOptions["onError"];
  };

  private _phase: ConnectionPhase = "idle";
  private _hydration: HydrationResult | null = null;
  private _reconnectTimer: unknown = null;
  private _stopped = false;
  private _abort: AbortController | null = null;

  constructor(options: RuntimeWebSocketClientOptions) {
    this._transport = options.transport;
    this._fetcher = options.fetcher ?? fetch;
    this._apiBaseUrl = options.apiBaseUrl;
    this._protocol = {
      expectedProtocolVersion: options.protocolVersion,
      allowAnyProtocolVersion: options.allowAnyProtocolVersion ?? false,
    };
    this._reconnect = new ReconnectScheduler(options.reconnect);
    this._heartbeat = new HeartbeatMonitor(options.heartbeat);
    this._diagnostics = new WebSocketDiagnostics(options.diagnostics);
    this._setTimer = options.setTimer ?? ((cb, ms) => setTimeout(cb, ms));
    this._clearTimer =
      options.clearTimer ?? ((id) => clearTimeout(id as ReturnType<typeof setTimeout>));
    this._hooks = {
      phase: options.onPhaseChange,
      connectionState: options.onConnectionStateChange,
      hydrated: options.onHydrated,
      envelope: options.onEnvelope,
      reject: options.onReject,
      error: options.onError,
    };
    this._transport.setListener((event) => this._onTransportEvent(event));
  }

  // ── identity ─────────────────────────────────────────────────────
  get phase(): ConnectionPhase {
    return this._phase;
  }

  get lastSequence(): number {
    return this._sequence.lastSequence;
  }

  get hydration(): HydrationResult | null {
    return this._hydration;
  }

  get reconnectAttempt(): number {
    return this._reconnect.attempt;
  }

  get diagnostics(): WebSocketDiagnostics {
    return this._diagnostics;
  }

  // ── lifecycle ────────────────────────────────────────────────────
  /** Start the client: hydrate, then connect. Safe to call after stop(). */
  async start(): Promise<void> {
    this._stopped = false;
    await this._hydrateThenConnect();
  }

  /** Tear down the client. Idempotent. */
  stop(): void {
    this._stopped = true;
    if (this._reconnectTimer !== null) {
      this._clearTimer(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._abort !== null) {
      this._abort.abort();
      this._abort = null;
    }
    this._heartbeat.stop();
    this._transport.close(1000, "client stop");
    this._setPhase("disconnected");
  }

  /** Force a fresh reconnect cycle. Used by tests + the diagnostics "reload" button. */
  forceReconnect(): void {
    if (this._stopped) return;
    this._transport.close(4000, "force reconnect");
  }

  subscribe(filter: SubscriptionFilter, listener: EnvelopeListener): Subscription {
    return this._subscriptions.add(filter, listener);
  }

  // ── hydration + connect ──────────────────────────────────────────
  private async _hydrateThenConnect(): Promise<void> {
    if (this._stopped) return;
    this._setPhase("hydrating");
    this._abort = new AbortController();
    try {
      const result = await fetchSnapshot({
        apiBaseUrl: this._apiBaseUrl,
        signal: this._abort.signal,
        fetcher: this._fetcher,
      });
      this._hydration = result;
      this._sequence.resnap(result.lastSequence);
      this._diagnostics.record({
        kind: "hydrate",
        lastSequence: result.lastSequence,
        runtimeId: result.runtimeId,
      });
      this._hooks.hydrated?.(result);
    } catch (error) {
      this._handleHydrationFailure(error);
      return;
    } finally {
      this._abort = null;
    }
    this._connect();
  }

  private _connect(): void {
    if (this._stopped) return;
    this._setPhase("connecting");
    const url = buildWebSocketUrl(this._transport.url, {
      sinceSequence: this._sequence.lastSequence,
    });
    if (isUrlAwareTransport(this._transport)) {
      this._transport.setUrl(url);
    }
    this._transport.open();
  }

  // ── transport handler ────────────────────────────────────────────
  private _onTransportEvent(event: TransportEvent): void {
    switch (event.kind) {
      case "open":
        this._handleOpen();
        break;
      case "message":
        this._handleMessage(event.data);
        break;
      case "error":
        this._hooks.error?.(new WebSocketClientError(event.message));
        break;
      case "close":
        this._handleClose();
        break;
    }
  }

  private _handleOpen(): void {
    this._reconnect.reset();
    this._setPhase("replaying");
    this._heartbeat.start(() => {
      this._diagnostics.record({ kind: "reject", reason: "stale", detail: "heartbeat" });
      this.forceReconnect();
    });
  }

  private _handleMessage(raw: string): void {
    const outcome = parseEnvelope(raw, this._protocol);
    if (outcome.kind !== "ok") {
      this._handleRejection(outcome);
      return;
    }
    const env = outcome.envelope;
    this._heartbeat.recordFrame(env.type === "heartbeat");
    // Snapshot envelopes resnap the cursor — they reflect a fresh
    // baseline rather than an incremental delta.
    if (env.type === "runtime_snapshot") {
      const last = (env.payload as { last_sequence?: number }).last_sequence;
      if (typeof last === "number") {
        this._sequence.resnap(last);
      }
      this._diagnostics.record({ kind: "frame", type: env.type, sequence: env.sequence ?? null });
      this._fanout(env);
      this._setPhase("live");
      return;
    }
    const decision = this._sequence.decide(env.sequence);
    if (decision === "duplicate") {
      this._sequence.recordDuplicate();
      this._diagnostics.record({ kind: "reject", reason: "duplicate" });
      this._hooks.reject?.("duplicate");
      return;
    }
    if (decision === "stale") {
      this._sequence.recordStale();
      this._diagnostics.record({ kind: "reject", reason: "stale" });
      this._hooks.reject?.("stale");
      return;
    }
    if (decision === "out-of-order") {
      this._sequence.recordOutOfOrder();
    }
    this._sequence.commit(env.sequence);
    this._diagnostics.record({ kind: "frame", type: env.type, sequence: env.sequence ?? null });
    // Any successfully-parsed envelope proves the transport is alive
    // and the server is talking. Flip out of every pre-live phase —
    // not just ``replaying`` — so the badge can't stick on
    // ``Connecting`` / ``Hydrating`` when messages are already
    // flowing (which previously happened when the websocket's
    // ``open`` event was missed or arrived after the first message
    // under load).
    if (this._isPreLivePhase(this._phase)) {
      this._setPhase("live");
    }
    this._fanout(env);
  }

  /** Pre-live phases the connection state machine can flip out of
   *  when proof of an active stream arrives (any envelope, any
   *  type).
   *
   *  ``disconnected`` and ``failed`` are TERMINAL — a stray late
   *  message after the user explicitly stopped, or after the
   *  reconnect-budget ran out, must NOT silently revive the
   *  connection state. The transport is closed by then; the
   *  appearance of "live" without an actual socket would be a lie.
   */
  private _isPreLivePhase(phase: ConnectionPhase): boolean {
    return (
      phase === "idle" ||
      phase === "hydrating" ||
      phase === "connecting" ||
      phase === "replaying" ||
      phase === "reconnecting"
    );
  }

  private _handleClose(): void {
    this._heartbeat.stop();
    if (this._stopped) {
      this._setPhase("disconnected");
      return;
    }
    this._scheduleReconnect();
  }

  private _handleRejection(outcome: ParseOutcome): void {
    if (outcome.kind === "ok") return;
    const reason = (
      outcome.kind === "protocol-mismatch"
        ? "protocol-mismatch"
        : outcome.kind === "unknown-type"
          ? "unknown-type"
          : outcome.kind === "invalid-json"
            ? "invalid-json"
            : "invalid-shape"
    ) as RejectReason;
    const detail =
      "message" in outcome
        ? outcome.message
        : "received" in outcome
          ? `${outcome.received} vs ${outcome.expected}`
          : "";
    this._diagnostics.record({ kind: "reject", reason, detail });
    this._hooks.reject?.(reason, detail);
  }

  // ── reconnect ────────────────────────────────────────────────────
  private _scheduleReconnect(): void {
    if (this._stopped) return;
    const schedule = this._reconnect.next();
    if (schedule === null) {
      this._setPhase("failed");
      return;
    }
    this._setPhase("reconnecting");
    this._diagnostics.record({
      kind: "reconnect",
      attempt: schedule.attempt,
      delayMs: schedule.delayMs,
    });
    this._reconnectTimer = this._setTimer(() => {
      this._reconnectTimer = null;
      this._connect();
    }, schedule.delayMs);
  }

  // ── hydration failure → fallback ─────────────────────────────────
  private _handleHydrationFailure(error: unknown): void {
    const err =
      error instanceof HydrationFailedError
        ? error
        : new HydrationFailedError(String(error), error);
    this._hooks.error?.(err);
    if (this._stopped) return;
    // Fall back to plain connect — the server's ``runtime_snapshot``
    // envelope on connect is the secondary hydration path. We keep
    // last_sequence at 0 so the server is free to send a full
    // snapshot rather than a since-cursor replay.
    this._sequence.reset(0);
    this._connect();
  }

  private _fanout(env: RuntimeEnvelope): void {
    this._hooks.envelope?.(env);
    this._subscriptions.emit(env);
  }

  private _setPhase(phase: ConnectionPhase): void {
    if (this._phase === phase) return;
    const from = this._phase;
    this._phase = phase;
    this._diagnostics.record({ kind: "phase", from, to: phase });
    this._hooks.phase?.(phase);
    this._hooks.connectionState?.(toConnectionState(phase));
    if (isTerminalPhase(phase)) {
      this._heartbeat.stop();
    }
  }
}
