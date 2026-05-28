/**
 * Snapshot hydration orchestrator.
 *
 * The websocket client calls :func:`fetchSnapshot` before opening the
 * socket. Hydration writes the snapshot to the Zustand store so the
 * UI has a baseline before the first delta lands, and returns the
 * canonical cursor (last_sequence + runtime_id) so the client can
 * supply ``since_sequence`` on the websocket handshake.
 *
 * Fetching uses ``fetch`` with an ``AbortController`` so the calling
 * client can cancel mid-flight (e.g. if the user clicks Disconnect
 * before the snapshot arrives).
 */

import type { RuntimeSnapshot } from "@/types/runtime";
import { HydrationFailedError } from "@/runtime/websocket/exceptions";

export interface HydrationResult {
  snapshot: RuntimeSnapshot;
  lastSequence: number;
  runtimeId: string;
}

export interface HydrationOptions {
  apiBaseUrl: string;
  signal?: AbortSignal;
  /** Pluggable fetcher — tests pass a stub. */
  fetcher?: typeof fetch;
}

/**
 * Pull ``GET /api/runtime/snapshot`` + return the parsed snapshot.
 *
 * Raises :class:`HydrationFailedError` on:
 *   * network error (offline backend, CORS issue)
 *   * non-2xx HTTP response
 *   * malformed JSON
 *   * snapshot missing the consistency cursor
 *
 * Callers catch + record the failure via
 * :func:`ClientMetrics.recordSnapshotHydrationFailure`.
 */
export async function fetchSnapshot(options: HydrationOptions): Promise<HydrationResult> {
  const { apiBaseUrl, signal, fetcher = fetch } = options;
  const url = `${apiBaseUrl}/api/runtime/snapshot`;
  let response: Response;
  try {
    response = await fetcher(url, { signal });
  } catch (cause) {
    throw new HydrationFailedError(`snapshot fetch failed: ${(cause as Error).message}`, cause);
  }
  if (!response.ok) {
    throw new HydrationFailedError(
      `snapshot fetch returned ${response.status} ${response.statusText}`,
    );
  }
  let snapshot: RuntimeSnapshot;
  try {
    snapshot = (await response.json()) as RuntimeSnapshot;
  } catch (cause) {
    throw new HydrationFailedError(
      `snapshot payload was not valid JSON: ${(cause as Error).message}`,
      cause,
    );
  }
  const consistency = snapshot?.consistency;
  if (consistency === undefined || typeof consistency.last_sequence !== "number") {
    throw new HydrationFailedError("snapshot payload missing consistency cursor");
  }
  const metadata = snapshot.metadata;
  if (metadata === undefined || typeof metadata.runtime_id !== "string") {
    throw new HydrationFailedError("snapshot payload missing runtime identity");
  }
  return {
    snapshot,
    lastSequence: consistency.last_sequence,
    runtimeId: metadata.runtime_id,
  };
}
