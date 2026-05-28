/**
 * Tests for HiDPI canvas helpers.
 *
 * jsdom provides a minimal canvas. We don't rely on any drawing
 * primitives — only the sizing + transform plumbing.
 */

import { describe, expect, it, vi } from "vitest";
import {
  prepareFrame,
  readDevicePixelRatio,
  resizeCanvasToViewport,
} from "@/dashboard/timeline/utils/canvas";

describe("resizeCanvasToViewport", () => {
  it("sets backing-store + CSS dimensions and returns true when changed", () => {
    const canvas = document.createElement("canvas");
    const changed = resizeCanvasToViewport(canvas, {
      cssWidth: 200,
      cssHeight: 100,
      devicePixelRatio: 2,
    });
    expect(changed).toBe(true);
    expect(canvas.width).toBe(400);
    expect(canvas.height).toBe(200);
    expect(canvas.style.width).toBe("200px");
    expect(canvas.style.height).toBe("100px");
  });

  it("is idempotent — repeated calls return false", () => {
    const canvas = document.createElement("canvas");
    const v = { cssWidth: 200, cssHeight: 100, devicePixelRatio: 2 };
    expect(resizeCanvasToViewport(canvas, v)).toBe(true);
    expect(resizeCanvasToViewport(canvas, v)).toBe(false);
  });
});

describe("prepareFrame", () => {
  it("resets the transform + clears", () => {
    const setTransform = vi.fn();
    const clearRect = vi.fn();
    const ctx = { setTransform, clearRect } as unknown as CanvasRenderingContext2D;
    prepareFrame(ctx, { cssWidth: 100, cssHeight: 50, devicePixelRatio: 2 });
    expect(setTransform).toHaveBeenCalledWith(2, 0, 0, 2, 0, 0);
    expect(clearRect).toHaveBeenCalledWith(0, 0, 100, 50);
  });
});

describe("readDevicePixelRatio", () => {
  it("returns 1 for invalid window values", () => {
    const original = window.devicePixelRatio;
    Object.defineProperty(window, "devicePixelRatio", { value: 0, configurable: true });
    expect(readDevicePixelRatio()).toBe(1);
    Object.defineProperty(window, "devicePixelRatio", { value: original, configurable: true });
  });
});
