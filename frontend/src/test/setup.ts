/**
 * Vitest setup file.
 *
 * Loaded once per test file (via the ``setupFiles`` config). Wires
 * up the testing-library matchers + a cleanup hook so each test
 * starts with a fresh DOM.
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom does not implement ResizeObserver; the replay timeline
// controls use it for layout-driven viewport tracking, so we stub
// it with a no-op implementation that the components can construct
// and use without crashing.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (typeof (globalThis as { ResizeObserver?: unknown }).ResizeObserver === "undefined") {
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver =
    ResizeObserverStub;
}

afterEach(() => {
  cleanup();
});
