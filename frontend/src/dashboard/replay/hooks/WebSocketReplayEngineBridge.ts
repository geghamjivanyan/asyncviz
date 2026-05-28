/**
 * WebSocket-backed :class:`ReplayEngineBridge`.
 *
 * Subscribes to ``replay_status`` envelopes on the canonical runtime
 * websocket, parses each payload into the controls' shape
 * (:type:`ReplaySessionWindow` + :type:`ReplayPlaybackSnapshot`), and
 * fans the updates out to the bridge's subscribers. The dashboard's
 * existing :func:`useReplayEngineBridge` hook is unmodified — this
 * bridge just plugs into the contract the in-memory test bridge
 * already satisfies.
 *
 * Control intents (play / pause / seek / set-speed) are accepted but
 * deliberately NOT dispatched to the backend in this commit — the
 * server-side control API doesn't exist yet. They land in a
 * recorded list so a future control endpoint can be wired without
 * touching the bridge's consumer surface.
 */

import type { RuntimeWebSocketClient } from "@/runtime/websocket";
import type { RuntimeEnvelope } from "@/types/runtime";
import type {
  ReplayBookmark,
  ReplayControlIntent,
  ReplayPlaybackSnapshot,
  ReplayPlaybackState,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";
import type {
  ReplayEngineBridge,
  ReplayEngineUnsubscribe,
} from "@/dashboard/replay/hooks/ReplayEngineBridge";

/** Default window when no ``replay_status`` envelope has arrived
 *  yet. ``maxSequence === 0`` is the SPA's "no recording loaded"
 *  signal — the bridge starts there and replaces it on the first
 *  envelope. */
const EMPTY_WINDOW: ReplaySessionWindow = {
  minSequence: 0,
  maxSequence: 0,
  minMonotonicNs: 0,
  maxMonotonicNs: 0,
};

/** Default playback before any envelope arrives. */
const EMPTY_PLAYBACK: ReplayPlaybackSnapshot = {
  state: "idle",
  speed: 1,
  lastSequence: 0,
  lastMonotonicNs: 0,
  framesDispatched: 0,
  paused: false,
};

const KNOWN_STATES: ReadonlySet<ReplayPlaybackState> = new Set<ReplayPlaybackState>([
  "idle",
  "playing",
  "paused",
  "seeking",
  "buffering",
  "stopped",
  "failed",
]);

interface ReplayStatusPayload {
  recording?: {
    bundle_id?: unknown;
    runtime_id?: unknown;
    event_count?: unknown;
    chunk_count?: unknown;
    snapshot_count?: unknown;
    last_sequence?: unknown;
    finalized?: unknown;
    source_label?: unknown;
  };
  window?: {
    min_sequence?: unknown;
    max_sequence?: unknown;
    min_monotonic_ns?: unknown;
    max_monotonic_ns?: unknown;
  };
  playback?: {
    state?: unknown;
    speed?: unknown;
    last_sequence?: unknown;
    last_monotonic_ns?: unknown;
    frames_dispatched?: unknown;
    queue_depth?: unknown;
    paused?: unknown;
    error_detail?: unknown;
  };
}

export interface WebSocketReplayEngineBridgeOptions {
  readonly client: RuntimeWebSocketClient;
}

export class WebSocketReplayEngineBridge implements ReplayEngineBridge {
  private _window: ReplaySessionWindow = EMPTY_WINDOW;
  private _playback: ReplayPlaybackSnapshot = EMPTY_PLAYBACK;
  private readonly _playbackListeners = new Set<
    (snapshot: ReplayPlaybackSnapshot) => void
  >();
  private readonly _markerListeners = new Set<
    (marker: ReplayTimelineMarker) => void
  >();
  private readonly _bookmarkListeners = new Set<
    (bookmarks: readonly ReplayBookmark[]) => void
  >();
  /** Public so debug tooling can confirm intent-dispatch wired. */
  readonly intents: ReplayControlIntent[] = [];
  private readonly _subscription: { unsubscribe: () => void };

  constructor(options: WebSocketReplayEngineBridgeOptions) {
    this._subscription = options.client.subscribe(
      "replay_status",
      (envelope) => this._onReplayStatus(envelope),
    );
  }

  // ── ReplayEngineBridge protocol ────────────────────────────────
  getSessionWindow(): ReplaySessionWindow {
    return this._window;
  }

  getPlaybackSnapshot(): ReplayPlaybackSnapshot {
    return this._playback;
  }

  subscribePlayback(
    listener: (snapshot: ReplayPlaybackSnapshot) => void,
  ): ReplayEngineUnsubscribe {
    this._playbackListeners.add(listener);
    return () => {
      this._playbackListeners.delete(listener);
    };
  }

  subscribeMarkers(
    listener: (marker: ReplayTimelineMarker) => void,
  ): ReplayEngineUnsubscribe {
    this._markerListeners.add(listener);
    return () => {
      this._markerListeners.delete(listener);
    };
  }

  subscribeBookmarks(
    listener: (bookmarks: readonly ReplayBookmark[]) => void,
  ): ReplayEngineUnsubscribe {
    this._bookmarkListeners.add(listener);
    return () => {
      this._bookmarkListeners.delete(listener);
    };
  }

  dispatch(intent: ReplayControlIntent): void {
    // Server-side control endpoint not implemented yet; capture so
    // the consumer surface stays correct + a future control path
    // can read them off this list.
    this.intents.push(intent);
  }

  /** Drop the websocket subscription. Tests + page unmount call this. */
  dispose(): void {
    this._subscription.unsubscribe();
    this._playbackListeners.clear();
    this._markerListeners.clear();
    this._bookmarkListeners.clear();
  }

  // ── envelope handler ───────────────────────────────────────────
  private _onReplayStatus(envelope: RuntimeEnvelope): void {
    const payload = envelope.payload as ReplayStatusPayload | undefined;
    if (payload === undefined) return;

    const window = this._coerceWindow(payload.window);
    if (window !== null) {
      this._window = window;
    }

    const playback = this._coercePlayback(payload.playback);
    if (playback !== null) {
      this._playback = playback;
      // Fan out the new snapshot to every subscriber. Listeners are
      // expected to be synchronous + cheap (store setters); any
      // throwing listener doesn't take down the others.
      for (const listener of this._playbackListeners) {
        try {
          listener(playback);
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error("replay playback listener threw", err);
        }
      }
    }
  }

  private _coerceWindow(
    raw: ReplayStatusPayload["window"],
  ): ReplaySessionWindow | null {
    if (raw === undefined) return null;
    const minSequence = toInt(raw.min_sequence, this._window.minSequence);
    const maxSequence = toInt(raw.max_sequence, this._window.maxSequence);
    const minMonotonicNs = toInt(raw.min_monotonic_ns, this._window.minMonotonicNs);
    const maxMonotonicNs = toInt(raw.max_monotonic_ns, this._window.maxMonotonicNs);
    return {
      minSequence,
      maxSequence,
      minMonotonicNs,
      maxMonotonicNs,
    };
  }

  private _coercePlayback(
    raw: ReplayStatusPayload["playback"],
  ): ReplayPlaybackSnapshot | null {
    if (raw === undefined) return null;
    const state = this._coerceState(raw.state);
    return {
      state,
      speed: toNumber(raw.speed, this._playback.speed),
      lastSequence: toInt(raw.last_sequence, this._playback.lastSequence),
      lastMonotonicNs: toInt(raw.last_monotonic_ns, this._playback.lastMonotonicNs),
      framesDispatched: toInt(raw.frames_dispatched, this._playback.framesDispatched),
      paused: toBool(raw.paused, this._playback.paused),
      errorDetail: typeof raw.error_detail === "string" && raw.error_detail !== ""
        ? raw.error_detail
        : undefined,
    };
  }

  private _coerceState(value: unknown): ReplayPlaybackState {
    if (typeof value !== "string") return this._playback.state;
    return KNOWN_STATES.has(value as ReplayPlaybackState)
      ? (value as ReplayPlaybackState)
      : this._playback.state;
  }
}

// ── tiny coercion helpers ──────────────────────────────────────────────


function toInt(value: unknown, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.trunc(value);
}

function toNumber(value: unknown, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return value;
}

function toBool(value: unknown, fallback: boolean): boolean {
  if (typeof value !== "boolean") return fallback;
  return value;
}
