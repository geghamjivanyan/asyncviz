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
  ReplayMarkerKind,
  ReplayMarkerSeverity,
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

const KNOWN_MARKER_KINDS: ReadonlySet<ReplayMarkerKind> = new Set<ReplayMarkerKind>([
  "warning",
  "saturation",
  "blocking",
  "checkpoint",
  "bookmark",
  "annotation",
]);

const KNOWN_SEVERITIES: ReadonlySet<ReplayMarkerSeverity> = new Set<ReplayMarkerSeverity>([
  "info",
  "warning",
  "critical",
]);

interface WireMarker {
  id?: unknown;
  kind?: unknown;
  severity?: unknown;
  sequence?: unknown;
  monotonic_ns?: unknown;
  label?: unknown;
  description?: unknown;
}

interface WireBookmark {
  id?: unknown;
  label?: unknown;
  sequence?: unknown;
  monotonic_ns?: unknown;
  note?: unknown;
  created_at_ms?: unknown;
}

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
  markers?: unknown;
  bookmarks?: unknown;
}

export interface WebSocketReplayEngineBridgeOptions {
  readonly client: RuntimeWebSocketClient;
}

export class WebSocketReplayEngineBridge implements ReplayEngineBridge {
  private _window: ReplaySessionWindow = EMPTY_WINDOW;
  private _playback: ReplayPlaybackSnapshot = EMPTY_PLAYBACK;
  private readonly _playbackListeners = new Set<(snapshot: ReplayPlaybackSnapshot) => void>();
  private readonly _markerListeners = new Set<(marker: ReplayTimelineMarker) => void>();
  private readonly _bookmarkListeners = new Set<(bookmarks: readonly ReplayBookmark[]) => void>();
  /** Marker ids already pushed to listeners — the broadcaster ships
   *  the full marker array on every replay_status envelope (~2 Hz) so
   *  consumers don't miss anything after a websocket reconnect, but
   *  the store action ``appendMarker`` doesn't dedup; we filter here. */
  private readonly _knownMarkerIds = new Set<string>();
  /** Snapshot of the last bookmark batch we emitted — used to skip
   *  fan-out when nothing actually changed across status pings. */
  private _lastBookmarksSignature = "";
  /** Public so debug tooling can confirm intent-dispatch wired. */
  readonly intents: ReplayControlIntent[] = [];
  private readonly _subscription: { unsubscribe: () => void };

  constructor(options: WebSocketReplayEngineBridgeOptions) {
    this._subscription = options.client.subscribe("replay_status", (envelope) =>
      this._onReplayStatus(envelope),
    );
  }

  // ── ReplayEngineBridge protocol ────────────────────────────────
  getSessionWindow(): ReplaySessionWindow {
    return this._window;
  }

  getPlaybackSnapshot(): ReplayPlaybackSnapshot {
    return this._playback;
  }

  subscribePlayback(listener: (snapshot: ReplayPlaybackSnapshot) => void): ReplayEngineUnsubscribe {
    this._playbackListeners.add(listener);
    return () => {
      this._playbackListeners.delete(listener);
    };
  }

  subscribeMarkers(listener: (marker: ReplayTimelineMarker) => void): ReplayEngineUnsubscribe {
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
    this._knownMarkerIds.clear();
    this._lastBookmarksSignature = "";
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

    this._applyMarkers(payload.markers);
    this._applyBookmarks(payload.bookmarks);
  }

  private _applyMarkers(raw: unknown): void {
    if (!Array.isArray(raw) || raw.length === 0) return;
    for (const entry of raw as WireMarker[]) {
      const marker = this._coerceMarker(entry);
      if (marker === null) continue;
      if (this._knownMarkerIds.has(marker.id)) continue;
      this._knownMarkerIds.add(marker.id);
      for (const listener of this._markerListeners) {
        try {
          listener(marker);
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error("replay marker listener threw", err);
        }
      }
    }
  }

  private _applyBookmarks(raw: unknown): void {
    if (!Array.isArray(raw)) return;
    const coerced: ReplayBookmark[] = [];
    for (const entry of raw as WireBookmark[]) {
      const bookmark = this._coerceBookmark(entry);
      if (bookmark !== null) coerced.push(bookmark);
    }
    // Cheap content-equality check — ids are stable so a sorted-id
    // concat is enough to skip no-op fan-outs on every status ping.
    const signature = coerced
      .map((b) => b.id)
      .sort()
      .join("");
    if (signature === this._lastBookmarksSignature) return;
    this._lastBookmarksSignature = signature;
    for (const listener of this._bookmarkListeners) {
      try {
        listener(coerced);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("replay bookmark listener threw", err);
      }
    }
  }

  private _coerceMarker(raw: WireMarker | null | undefined): ReplayTimelineMarker | null {
    if (raw === null || typeof raw !== "object") return null;
    const id = typeof raw.id === "string" ? raw.id : null;
    const kind =
      typeof raw.kind === "string" && KNOWN_MARKER_KINDS.has(raw.kind as ReplayMarkerKind)
        ? (raw.kind as ReplayMarkerKind)
        : null;
    const severity =
      typeof raw.severity === "string" && KNOWN_SEVERITIES.has(raw.severity as ReplayMarkerSeverity)
        ? (raw.severity as ReplayMarkerSeverity)
        : null;
    const sequence =
      typeof raw.sequence === "number" && Number.isFinite(raw.sequence)
        ? Math.trunc(raw.sequence)
        : null;
    const monotonicNs =
      typeof raw.monotonic_ns === "number" && Number.isFinite(raw.monotonic_ns)
        ? Math.trunc(raw.monotonic_ns)
        : null;
    const label = typeof raw.label === "string" ? raw.label : null;
    if (
      id === null ||
      kind === null ||
      severity === null ||
      sequence === null ||
      monotonicNs === null ||
      label === null
    ) {
      return null;
    }
    const description =
      typeof raw.description === "string" && raw.description !== "" ? raw.description : undefined;
    return { id, kind, severity, sequence, monotonicNs, label, description };
  }

  private _coerceBookmark(raw: WireBookmark | null | undefined): ReplayBookmark | null {
    if (raw === null || typeof raw !== "object") return null;
    const id = typeof raw.id === "string" ? raw.id : null;
    const label = typeof raw.label === "string" ? raw.label : null;
    const sequence =
      typeof raw.sequence === "number" && Number.isFinite(raw.sequence)
        ? Math.trunc(raw.sequence)
        : null;
    const monotonicNs =
      typeof raw.monotonic_ns === "number" && Number.isFinite(raw.monotonic_ns)
        ? Math.trunc(raw.monotonic_ns)
        : null;
    if (id === null || label === null || sequence === null || monotonicNs === null) {
      return null;
    }
    const createdAtMs =
      typeof raw.created_at_ms === "number" && Number.isFinite(raw.created_at_ms)
        ? Math.trunc(raw.created_at_ms)
        : 0;
    const note = typeof raw.note === "string" && raw.note !== "" ? raw.note : undefined;
    return { id, label, sequence, monotonicNs, note, createdAtMs };
  }

  private _coerceWindow(raw: ReplayStatusPayload["window"]): ReplaySessionWindow | null {
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

  private _coercePlayback(raw: ReplayStatusPayload["playback"]): ReplayPlaybackSnapshot | null {
    if (raw === undefined) return null;
    const state = this._coerceState(raw.state);
    return {
      state,
      speed: toNumber(raw.speed, this._playback.speed),
      lastSequence: toInt(raw.last_sequence, this._playback.lastSequence),
      lastMonotonicNs: toInt(raw.last_monotonic_ns, this._playback.lastMonotonicNs),
      framesDispatched: toInt(raw.frames_dispatched, this._playback.framesDispatched),
      paused: toBool(raw.paused, this._playback.paused),
      errorDetail:
        typeof raw.error_detail === "string" && raw.error_detail !== ""
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
