/**
 * Pure helpers for encoding + decoding the selection state.
 *
 * The helpers are URL-safe + replay-friendly: the persisted payload
 * is a stable task id string. Future bookmarks / shareable links can
 * push the same payload through ``decodeSelection`` to restore the
 * exact selection.
 *
 * The module deliberately ships no I/O — actual storage lives in
 * future tasks (URL params, localStorage, replay bookmarks).
 */

export interface SelectionPersistencePayload {
  /** Persisted task id, or ``null`` when no selection was active. */
  selectedTaskId: string | null;
}

export function encodeSelection(taskId: string | null): SelectionPersistencePayload {
  return { selectedTaskId: taskId };
}

export function decodeSelection(payload: unknown): SelectionPersistencePayload {
  if (payload === null || payload === undefined) return { selectedTaskId: null };
  if (typeof payload === "string" && payload.length > 0) {
    return { selectedTaskId: payload };
  }
  if (
    typeof payload === "object" &&
    payload !== null &&
    "selectedTaskId" in payload &&
    typeof (payload as { selectedTaskId: unknown }).selectedTaskId === "string"
  ) {
    return { selectedTaskId: (payload as { selectedTaskId: string }).selectedTaskId };
  }
  return { selectedTaskId: null };
}

/** Pure: ``true`` when two payloads describe the same selection. */
export function selectionPayloadsEqual(
  a: SelectionPersistencePayload,
  b: SelectionPersistencePayload,
): boolean {
  return a.selectedTaskId === b.selectedTaskId;
}
