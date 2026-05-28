/**
 * Test helper — install a richer ``getContext('2d')`` mock that
 * supports the methods the row renderer relies on (``save`` /
 * ``restore`` / ``measureText`` / ``setLineDash`` / ``createPattern``).
 *
 * The mock is intentionally cheap: ``measureText`` returns a width
 * roughly proportional to the string length so binary-search
 * truncation behaves deterministically.
 */

import { vi } from "vitest";

export interface RowFakeContext extends Record<string, unknown> {
  // canvas drawing surface (subset used by the row + segment renderers).
  setTransform: (...args: unknown[]) => void;
  clearRect: (...args: unknown[]) => void;
  fillRect: (...args: unknown[]) => void;
  strokeRect: (...args: unknown[]) => void;
  beginPath: (...args: unknown[]) => void;
  closePath: (...args: unknown[]) => void;
  moveTo: (...args: unknown[]) => void;
  lineTo: (...args: unknown[]) => void;
  quadraticCurveTo: (...args: unknown[]) => void;
  rect: (...args: unknown[]) => void;
  arc: (...args: unknown[]) => void;
  clip: (...args: unknown[]) => void;
  stroke: (...args: unknown[]) => void;
  fill: (...args: unknown[]) => void;
  fillText: (...args: unknown[]) => void;
  save: (...args: unknown[]) => void;
  restore: (...args: unknown[]) => void;
  setLineDash: (...args: unknown[]) => void;
  measureText: (text: string) => { width: number };
  createPattern: (...args: unknown[]) => null;
  fillStyle: string;
  strokeStyle: string;
  lineWidth: number;
  font: string;
  textBaseline: string;
  textAlign: string;
}

/** Build a fresh mock context with deterministic measureText. */
export function createRowFakeContext(): RowFakeContext {
  const ctx: RowFakeContext = {
    setTransform: vi.fn(),
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    quadraticCurveTo: vi.fn(),
    rect: vi.fn(),
    arc: vi.fn(),
    clip: vi.fn(),
    stroke: vi.fn(),
    fill: vi.fn(),
    fillText: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    setLineDash: vi.fn(),
    measureText: (text: string) => ({ width: text.length * 6 }),
    createPattern: () => null,
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    font: "12px sans-serif",
    textBaseline: "alphabetic",
    textAlign: "left",
  };
  return ctx;
}

/** Replace ``HTMLCanvasElement.prototype.getContext`` for the duration
 *  of the test file. Returns a restore function. */
export function installRowFakeCanvasContext(): () => void {
  const original = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function getContext(): RenderingContext {
    return createRowFakeContext() as unknown as RenderingContext;
  } as unknown as typeof HTMLCanvasElement.prototype.getContext;
  return () => {
    HTMLCanvasElement.prototype.getContext = original;
  };
}
