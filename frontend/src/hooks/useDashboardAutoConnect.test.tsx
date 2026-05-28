/**
 * Tests for :func:`useDashboardAutoConnect`.
 *
 * The hook owns the dashboard shell's mount/unmount lifecycle:
 *
 *   * Mount → connect() must fire exactly once (the underlying
 *     :func:`useHydrateRuntime` guards on a binding ref, so even
 *     React 18 StrictMode double-mounts result in one effective
 *     start.)
 *   * Unmount → disconnect() must fire, returning the client to a
 *     closed state.
 *
 * The websocket client is stubbed with the minimum surface
 * :func:`bindClientToStore` + the auto-connect hook need so the test
 * never opens a real socket.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render } from "@testing-library/react";
import { RuntimeProvider } from "@/app/providers/RuntimeProvider";
import { ConfigProvider } from "@/app/providers/ConfigProvider";
import { createTestConfig } from "@/app/configuration/runtimeConfig";
import { useDashboardAutoConnect } from "@/hooks/useDashboardAutoConnect";
import type { RuntimeWebSocketClient } from "@/runtime/websocket";
import { useRuntimeStore } from "@/state/runtime/store";

class FakeWebSocketClient {
  startCalls = 0;
  stopCalls = 0;
  subscribeCalls = 0;
  unsubscribeCalls = 0;
  reconnectAttempt = 0;
  _hooks: {
    phase?: (phase: string) => void;
    hydrated?: (result: unknown) => void;
  } = {};

  async start(): Promise<void> {
    this.startCalls += 1;
    // Mirror the production client's phase progression so the store
    // moves from "idle" to "live" — this is what the dashboard UI
    // would observe.
    this._hooks.phase?.("hydrating");
    this._hooks.phase?.("connecting");
    this._hooks.phase?.("replaying");
    this._hooks.phase?.("live");
  }

  stop(): void {
    this.stopCalls += 1;
    this._hooks.phase?.("disconnected");
  }

  subscribe(_filter: string, _listener: (envelope: unknown) => void) {
    this.subscribeCalls += 1;
    return {
      unsubscribe: () => {
        this.unsubscribeCalls += 1;
      },
    };
  }
}

function makeFake(): FakeWebSocketClient {
  return new FakeWebSocketClient();
}

function ShellHarness({ children }: { children?: React.ReactNode }) {
  // Drives the same hook the real DashboardShell renders via
  // ShellInstrumentation. Returns null content so we can assert on
  // the store + the fake client rather than DOM nodes.
  useDashboardAutoConnect();
  return <>{children ?? null}</>;
}

function renderShell(fake: FakeWebSocketClient) {
  const config = createTestConfig();
  return render(
    <ConfigProvider config={config}>
      <RuntimeProvider webSocketClient={fake as unknown as RuntimeWebSocketClient}>
        <ShellHarness />
      </RuntimeProvider>
    </ConfigProvider>,
  );
}

describe("useDashboardAutoConnect", () => {
  afterEach(() => {
    useRuntimeStore.getState().reset();
  });

  it("calls client.start() exactly once on mount", async () => {
    const fake = makeFake();
    renderShell(fake);
    // ``start`` is async — flush the microtask so the awaited path
    // completes before we assert.
    await act(async () => {
      await Promise.resolve();
    });
    expect(fake.startCalls).toBe(1);
  });

  it("subscribes a wildcard listener on mount", async () => {
    const fake = makeFake();
    renderShell(fake);
    await act(async () => {
      await Promise.resolve();
    });
    // bindClientToStore registers one wildcard subscription.
    expect(fake.subscribeCalls).toBe(1);
  });

  it("drives the store out of the idle phase", async () => {
    const fake = makeFake();
    renderShell(fake);
    await act(async () => {
      await Promise.resolve();
    });
    const state = useRuntimeStore.getState();
    expect(state.connection.phase).toBe("live");
    expect(state.connection.state).toBe("open");
  });

  it("calls client.stop() + unsubscribes on unmount", async () => {
    const fake = makeFake();
    const { unmount } = renderShell(fake);
    await act(async () => {
      await Promise.resolve();
    });
    unmount();
    expect(fake.stopCalls).toBeGreaterThanOrEqual(1);
    expect(fake.unsubscribeCalls).toBeGreaterThanOrEqual(1);
  });

  it("does not double-start when the effect re-runs without a real client swap", async () => {
    const fake = makeFake();
    const { rerender } = renderShell(fake);
    await act(async () => {
      await Promise.resolve();
    });
    // Re-render with the same provider state. Because connect/disconnect
    // come from useCallback with stable deps, the effect should NOT
    // re-fire, and the inner binding guard means start is not called
    // again even if the effect did fire.
    rerender(
      <ConfigProvider config={createTestConfig()}>
        <RuntimeProvider webSocketClient={fake as unknown as RuntimeWebSocketClient}>
          <ShellHarness />
        </RuntimeProvider>
      </ConfigProvider>,
    );
    await act(async () => {
      await Promise.resolve();
    });
    // The fresh ConfigProvider creates a fresh config object identity
    // but the websocket client is still the same fake instance, so
    // the RuntimeProvider's useMemo returns its existing value. The
    // binding-ref guard inside useHydrateRuntime keeps the call count
    // at 1.
    expect(fake.startCalls).toBe(1);
  });

  it("re-starts after an explicit unmount → remount cycle", async () => {
    const fake = makeFake();
    vi.useFakeTimers({ shouldAdvanceTime: false });
    const { unmount } = renderShell(fake);
    await act(async () => {
      await Promise.resolve();
    });
    unmount();
    // Brand-new render = brand-new providers = brand-new client. But
    // the test uses the same fake to verify start/stop accounting.
    renderShell(fake);
    await act(async () => {
      await Promise.resolve();
    });
    expect(fake.startCalls).toBe(2);
    expect(fake.stopCalls).toBeGreaterThanOrEqual(1);
    vi.useRealTimers();
  });
});
