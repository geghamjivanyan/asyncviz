/**
 * Overlay scheduler.
 *
 * Overlays (selection ring, replay cursor, hover crosshair, mini-map
 * highlights) redraw at much higher frequency than the data layer.
 * Painting them inside the main pass forces full-data redraws every
 * frame; the scheduler isolates them so the data layer renders only
 * when *its* inputs change.
 *
 * The scheduler exposes a tick-style API. Callers
 * :meth:`requestOverlayRedraw`; the scheduler tracks pending overlays
 * + coalesces them; the pipeline flushes them after the data pass.
 */

import type { DirtyRegion } from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import { mergeRegions } from "@/dashboard/timeline/rendering_optimization/models/dirty_region";

export interface OverlayDescriptor {
  readonly id: string;
  /** Whether this overlay is included in coalesced redraws.
   *  ``false`` means it always redraws on a dirty bit. */
  readonly coalesce: boolean;
}

interface OverlayState {
  readonly descriptor: OverlayDescriptor;
  dirty: boolean;
  region: DirtyRegion | null;
}

export interface OverlayStats {
  readonly overlaysRegistered: number;
  readonly overlaysDirty: number;
  readonly overlayRedraws: number;
  readonly coalesced: number;
}

export class TimelineOverlayScheduler {
  private readonly overlays = new Map<string, OverlayState>();
  private overlayRedraws = 0;
  private coalesced = 0;

  register(descriptor: OverlayDescriptor): void {
    if (this.overlays.has(descriptor.id)) return;
    this.overlays.set(descriptor.id, {
      descriptor,
      dirty: false,
      region: null,
    });
  }

  unregister(id: string): void {
    this.overlays.delete(id);
  }

  /** Schedule an overlay redraw. Region is optional; ``null`` means
   *  "redraw the whole overlay surface". */
  requestOverlayRedraw(id: string, region: DirtyRegion | null): void {
    const overlay = this.overlays.get(id);
    if (overlay === undefined) return;
    if (overlay.dirty && overlay.descriptor.coalesce) {
      this.coalesced += 1;
      if (overlay.region !== null && region !== null) {
        overlay.region = mergeRegions(overlay.region, region);
      } else if (region !== null) {
        overlay.region = region;
      }
      return;
    }
    overlay.dirty = true;
    overlay.region = region;
  }

  /** Drain every dirty overlay + return what to redraw. Marks each
   *  overlay clean. */
  flush(): readonly { id: string; region: DirtyRegion | null }[] {
    const out: { id: string; region: DirtyRegion | null }[] = [];
    for (const overlay of this.overlays.values()) {
      if (!overlay.dirty) continue;
      out.push({ id: overlay.descriptor.id, region: overlay.region });
      this.overlayRedraws += 1;
      overlay.dirty = false;
      overlay.region = null;
    }
    return out;
  }

  /** Snapshot which overlays are dirty without consuming them. */
  pendingOverlays(): readonly string[] {
    const out: string[] = [];
    for (const overlay of this.overlays.values()) {
      if (overlay.dirty) out.push(overlay.descriptor.id);
    }
    return out;
  }

  isDirty(): boolean {
    for (const overlay of this.overlays.values()) {
      if (overlay.dirty) return true;
    }
    return false;
  }

  stats(): OverlayStats {
    let dirty = 0;
    for (const overlay of this.overlays.values()) {
      if (overlay.dirty) dirty += 1;
    }
    return {
      overlaysRegistered: this.overlays.size,
      overlaysDirty: dirty,
      overlayRedraws: this.overlayRedraws,
      coalesced: this.coalesced,
    };
  }

  clear(): void {
    this.overlays.clear();
    this.overlayRedraws = 0;
    this.coalesced = 0;
  }
}
