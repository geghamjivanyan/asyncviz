/**
 * Test helper — install a fake ``getContext('2d')`` on every canvas.
 *
 * jsdom does not implement the canvas drawing surface; the renderer
 * defensively no-ops when ``getContext`` returns ``null``, but for
 * tests that *do* want the renderer to run we install a minimal
 * stub.
 */

import { vi } from "vitest";

export interface FakeCanvasContext {
  setTransform: ReturnType<typeof vi.fn>;
  clearRect: ReturnType<typeof vi.fn>;
  fillRect: ReturnType<typeof vi.fn>;
  strokeRect: ReturnType<typeof vi.fn>;
  beginPath: ReturnType<typeof vi.fn>;
  moveTo: ReturnType<typeof vi.fn>;
  lineTo: ReturnType<typeof vi.fn>;
  stroke: ReturnType<typeof vi.fn>;
  fill: ReturnType<typeof vi.fn>;
  fillStyle: string;
  strokeStyle: string;
  lineWidth: number;
}

export function createFakeContext(): FakeCanvasContext {
  return {
    setTransform: vi.fn(),
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    fill: vi.fn(),
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
  };
}

/** Replace ``HTMLCanvasElement.prototype.getContext`` for the duration
 *  of the test file. Returns a function that restores the original. */
export function installFakeCanvasContext(): () => void {
  const original = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function getContext(): RenderingContext {
    return createFakeContext() as unknown as RenderingContext;
  } as unknown as typeof HTMLCanvasElement.prototype.getContext;
  return () => {
    HTMLCanvasElement.prototype.getContext = original;
  };
}
