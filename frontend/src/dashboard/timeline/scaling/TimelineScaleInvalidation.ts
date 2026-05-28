/**
 * Invalidation hooks consumed by the scaling engine.
 *
 * The scale engine has three kinds of invalidation:
 *
 *   * scale-window changes — pan / zoom / fit,
 *   * viewport changes — width or DPR changed,
 *   * constraint changes — limits widened/narrowed.
 *
 * The interface lets future consumers (e.g. a synchronized-cursor
 * controller) listen for the precise change kind without inspecting
 * the engine's internals.
 */

export type ScaleInvalidationKind =
  | "scale-window"
  | "viewport"
  | "constraints"
  | "manual";

export type ScaleInvalidationListener = (kind: ScaleInvalidationKind) => void;

export class ScaleInvalidationBus {
  private listeners = new Set<ScaleInvalidationListener>();
  private _emitted = 0;

  subscribe(listener: ScaleInvalidationListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  emit(kind: ScaleInvalidationKind): void {
    this._emitted += 1;
    for (const listener of this.listeners) {
      try {
        listener(kind);
      } catch (err) {
        console.error("ScaleInvalidationBus: listener threw", err);
      }
    }
  }

  size(): number {
    return this.listeners.size;
  }

  totalEmitted(): number {
    return this._emitted;
  }

  clear(): void {
    this.listeners.clear();
  }
}
