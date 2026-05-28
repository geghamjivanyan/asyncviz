/**
 * Layer manager.
 *
 * Groups render passes into ordered, prioritized layers + tracks which
 * layers are currently invalidated. The pipeline asks the manager for
 * "layers that need redrawing"; the answer is the smallest set
 * compatible with the active dirty regions + degradation strategies.
 *
 * The manager is intentionally decoupled from the existing
 * :class:`TimelineSceneGraph` — the scene graph holds canvas-level
 * layers; this manager holds *render passes* with priorities + dirty
 * tracking that the optimization layer can reason about.
 */

import type {
  DirtyRegion,
  DirtyRegionReason,
} from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import { mergeRegions } from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import { type RenderPriority } from "@/dashboard/timeline/rendering_optimization/models/render_priority";
import type { RenderPass } from "@/dashboard/timeline/rendering_optimization/models/render_pass";

export interface LayerDescriptor {
  /** Stable layer id. */
  readonly id: string;
  /** Render priority — higher runs first + survives longer. */
  readonly priority: RenderPriority;
  /** Set of reasons that invalidate this layer. */
  readonly invalidatedBy: ReadonlySet<DirtyRegionReason>;
  /** Human-readable label. */
  readonly label: string;
}

interface LayerState {
  readonly descriptor: LayerDescriptor;
  dirty: boolean;
  regions: DirtyRegion[];
}

export interface LayerManagerStats {
  readonly layersRegistered: number;
  readonly layersDirty: number;
  readonly passesProduced: number;
}

export class TimelineLayerManager {
  private readonly layers = new Map<string, LayerState>();
  private passesProduced = 0;

  register(descriptor: LayerDescriptor): void {
    if (this.layers.has(descriptor.id)) {
      throw new Error(`layer already registered: ${descriptor.id}`);
    }
    this.layers.set(descriptor.id, {
      descriptor,
      dirty: true,
      regions: [],
    });
  }

  unregister(id: string): void {
    this.layers.delete(id);
  }

  /** Mark a region dirty + invalidate every layer that subscribes to
   *  the region's reason. */
  invalidate(region: DirtyRegion): void {
    for (const layer of this.layers.values()) {
      if (!layer.descriptor.invalidatedBy.has(region.reason)) continue;
      layer.dirty = true;
      if (layer.regions.length === 0) {
        layer.regions.push(region);
      } else {
        layer.regions[0] = mergeRegions(layer.regions[0]!, region);
      }
    }
  }

  /** Force-invalidate every layer (used on viewport/data changes). */
  invalidateAll(region: DirtyRegion): void {
    for (const layer of this.layers.values()) {
      layer.dirty = true;
      if (layer.regions.length === 0) layer.regions.push(region);
      else layer.regions[0] = mergeRegions(layer.regions[0]!, region);
    }
  }

  /** Render passes in priority-descending order. Only dirty layers
   *  appear in the output. */
  collectPasses(): RenderPass[] {
    const dirty: RenderPass[] = [];
    for (const layer of this.layers.values()) {
      if (!layer.dirty) continue;
      dirty.push({
        id: layer.descriptor.id,
        priority: layer.descriptor.priority,
        regions: layer.regions.slice(),
        label: layer.descriptor.label,
        degraded: false,
      });
    }
    dirty.sort((a, b) => b.priority - a.priority);
    this.passesProduced += dirty.length;
    return dirty;
  }

  /** Mark a layer as cleanly rendered. */
  acknowledge(id: string): void {
    const layer = this.layers.get(id);
    if (layer === undefined) return;
    layer.dirty = false;
    layer.regions.length = 0;
  }

  acknowledgeAll(): void {
    for (const layer of this.layers.values()) {
      layer.dirty = false;
      layer.regions.length = 0;
    }
  }

  stats(): LayerManagerStats {
    let layersDirty = 0;
    for (const layer of this.layers.values()) {
      if (layer.dirty) layersDirty += 1;
    }
    return {
      layersRegistered: this.layers.size,
      layersDirty,
      passesProduced: this.passesProduced,
    };
  }

  /** Snapshot of every layer's current dirty state. Used by
   *  diagnostics. */
  describe(): readonly { readonly id: string; readonly dirty: boolean }[] {
    return Array.from(this.layers.values(), (l) => ({
      id: l.descriptor.id,
      dirty: l.dirty,
    }));
  }

  has(id: string): boolean {
    return this.layers.has(id);
  }

  clear(): void {
    this.layers.clear();
    this.passesProduced = 0;
  }
}
