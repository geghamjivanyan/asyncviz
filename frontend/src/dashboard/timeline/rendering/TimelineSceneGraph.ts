/**
 * Layer registry + ordering.
 *
 * The scene graph is intentionally tiny — layers are added once, the
 * graph keeps them ordered. The renderer iterates the ordered list
 * every frame. Adding a layer doesn't trigger any side effect; the
 * renderer schedules its next frame via the scheduler.
 */

import type { RenderContext, TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";

export class TimelineSceneGraph {
  private layers: TimelineLayer[] = [];

  addLayer(layer: TimelineLayer): void {
    if (this.layers.some((l) => l.id === layer.id)) {
      throw new Error(`Layer "${layer.id}" already registered`);
    }
    this.layers.push(layer);
    this.layers.sort((a, b) => a.order - b.order);
  }

  removeLayer(id: string): void {
    this.layers = this.layers.filter((l) => l.id !== id);
  }

  layerIds(): readonly string[] {
    return this.layers.map((l) => l.id);
  }

  setLayerEnabled(id: string, enabled: boolean): void {
    const layer = this.layers.find((l) => l.id === id);
    if (layer !== undefined) layer.enabled = enabled;
  }

  /** Iterate every enabled layer in order. */
  renderAll(context: RenderContext): void {
    for (const layer of this.layers) {
      if (!layer.enabled) continue;
      layer.render(context);
    }
  }
}
