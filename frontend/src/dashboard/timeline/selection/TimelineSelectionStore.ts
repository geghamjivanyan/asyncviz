/**
 * Bridge between the canonical runtime store and the selection
 * controller.
 *
 * The runtime store already owns ``selectedTaskId`` + ``selectTask``.
 * This adapter wraps those primitives so the controller never
 * depends on Zustand directly — tests pass plain functions, the
 * React glue passes the store-backed implementation.
 */

import { useRuntimeStore } from "@/state/runtime";

/** Tiny store contract the controller depends on. */
export interface SelectionStore {
  getSelectedTaskId(): string | null;
  setSelectedTaskId(taskId: string | null): void;
  subscribe(listener: (taskId: string | null) => void): () => void;
}

/** Build a :type:`SelectionStore` backed by the runtime store. */
export function makeRuntimeSelectionStore(): SelectionStore {
  return {
    getSelectedTaskId: () => useRuntimeStore.getState().selectedTaskId,
    setSelectedTaskId: (taskId) => useRuntimeStore.getState().selectTask(taskId),
    subscribe: (listener) =>
      useRuntimeStore.subscribe((state, prev) => {
        if (state.selectedTaskId !== prev.selectedTaskId) {
          listener(state.selectedTaskId);
        }
      }),
  };
}
