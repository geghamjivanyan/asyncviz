/**
 * Tiny imperative focus-action surface the timeline container fills
 * and the inspector consumes.
 *
 * Keeping the indirection at the dashboard level means the timeline
 * doesn't import the inspector and vice versa — the page wires them
 * via a shared object.
 */

import { useRef, useCallback } from "react";

export interface InspectorFocusActions {
  reveal: () => void;
  fit: () => void;
}

export interface InspectorFocusBridge {
  /** Imperative actions the inspector calls. */
  actions: InspectorFocusActions;
  /** Setter the timeline calls to publish its current actions. */
  setActions: (next: Partial<InspectorFocusActions>) => void;
}

const NOOP = (): void => {
  /* default — nothing to do until the timeline publishes actions. */
};

/** Build a stable focus bridge — hold the result in component-local
 *  state so children rerender when the actions change. */
export function useInspectorFocusBridge(): InspectorFocusBridge {
  const revealRef = useRef<() => void>(NOOP);
  const fitRef = useRef<() => void>(NOOP);

  const actions = useRef<InspectorFocusActions>({
    reveal: () => revealRef.current(),
    fit: () => fitRef.current(),
  }).current;

  const setActions = useCallback((next: Partial<InspectorFocusActions>) => {
    if (next.reveal) revealRef.current = next.reveal;
    if (next.fit) fitRef.current = next.fit;
  }, []);

  return { actions, setActions };
}
