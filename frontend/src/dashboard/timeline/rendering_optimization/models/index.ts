/** Barrel for rendering_optimization model types. */

export type { DirtyRegion, DirtyRegionReason } from "./dirty_region";
export {
  FULL_REGION_SENTINEL,
  isFullRegion,
  mergeRegions,
  regionArea,
  regionsOverlap,
} from "./dirty_region";

export { RenderPriority, isRenderPriority } from "./render_priority";

export type { RenderPass, RenderPassResult } from "./render_pass";

export type { CacheNamespace } from "./cache_key";
export { makeCacheKey, makeVersionedKey, quantizeCoord } from "./cache_key";
