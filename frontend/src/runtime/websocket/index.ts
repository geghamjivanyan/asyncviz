/**
 * Public surface of the canonical websocket client.
 */

export { RuntimeWebSocketClient } from "@/runtime/websocket/client";
export type { RejectReason, RuntimeWebSocketClientOptions } from "@/runtime/websocket/client";

export {
  HydrationFailedError,
  ProtocolMismatchError,
  TransportNotOpenError,
  WebSocketClientError,
} from "@/runtime/websocket/exceptions";

export {
  isConnectingPhase,
  isLivePhase,
  isTerminalPhase,
  phaseRank,
  toConnectionState,
} from "@/runtime/websocket/lifecycle";
export type { ConnectionPhase } from "@/runtime/websocket/lifecycle";

export { KNOWN_ENVELOPE_TYPES, parseEnvelope } from "@/runtime/websocket/protocol";
export type { ParseOutcome, ProtocolOptions } from "@/runtime/websocket/protocol";

export {
  DEFAULT_BASE_DELAY_MS,
  DEFAULT_JITTER,
  DEFAULT_MAX_DELAY_MS,
  ReconnectScheduler,
} from "@/runtime/websocket/reconnect";
export type { ReconnectOptions, ReconnectSchedule } from "@/runtime/websocket/reconnect";

export { DEFAULT_STALE_THRESHOLD_MS, HeartbeatMonitor } from "@/runtime/websocket/heartbeat";
export type { HeartbeatOptions } from "@/runtime/websocket/heartbeat";

export { SequenceTracker } from "@/runtime/websocket/sequencing";
export type { SequenceDecision, SequenceTrackerSnapshot } from "@/runtime/websocket/sequencing";

export { SubscriptionRegistry } from "@/runtime/websocket/subscriptions";
export type {
  EnvelopeListener,
  Subscription,
  SubscriptionFilter,
} from "@/runtime/websocket/subscriptions";

export { fetchSnapshot } from "@/runtime/websocket/hydration";
export type { HydrationOptions, HydrationResult } from "@/runtime/websocket/hydration";

export { NativeWebSocketTransport } from "@/runtime/websocket/transport";
export type {
  TransportEvent,
  TransportEventListener,
  TransportReadyState,
  WebSocketTransport,
} from "@/runtime/websocket/transport";

export { buildWebSocketUrl } from "@/runtime/websocket/url";
export type { WebSocketUrlOptions } from "@/runtime/websocket/url";

export { WebSocketDiagnostics } from "@/runtime/websocket/diagnostics";
export type { DiagnosticsOptions, TraceEvent } from "@/runtime/websocket/diagnostics";
