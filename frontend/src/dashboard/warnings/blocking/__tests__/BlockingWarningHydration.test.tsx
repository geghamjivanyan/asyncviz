import { beforeEach, describe, expect, it, vi } from "vitest";
import { useEffect } from "react";
import { waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import {
  blockingWarningSnapshotUrl,
  useBlockingWarningHydration,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningHydration";
import { resetBlockingWarningPanelMetrics } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";
import { makeSnapshot } from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

beforeEach(() => {
  useBlockingWarningStore.getState().reset();
  resetBlockingWarningPanelMetrics();
});

function HydrationHarness({ fetcher }: { fetcher: typeof fetch }) {
  useBlockingWarningHydration({ fetcher });
  useEffect(() => {
    // touch the store so React subscribes — keeps the harness honest.
  });
  return null;
}

describe("useBlockingWarningHydration", () => {
  it("folds a successful snapshot into the store", async () => {
    const snapshot = makeSnapshot();
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => snapshot,
    } as Response);
    renderWithProviders(<HydrationHarness fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => {
      expect(useBlockingWarningStore.getState().status).toBe("ready");
    });
    expect(useBlockingWarningStore.getState().runtimeId).toBe(snapshot.runtime_id);
    expect(fetcher).toHaveBeenCalledWith(
      blockingWarningSnapshotUrl(""),
      expect.objectContaining({ signal: expect.any(Object) }),
    );
  });

  it("records an error on non-ok response", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "boom",
      json: async () => ({}),
    } as Response);
    renderWithProviders(<HydrationHarness fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => {
      expect(useBlockingWarningStore.getState().status).toBe("error");
    });
    expect(useBlockingWarningStore.getState().errorMessage).toMatch(/HTTP 503/);
  });
});

describe("blockingWarningSnapshotUrl", () => {
  it("joins same-origin (empty base) cleanly", () => {
    expect(blockingWarningSnapshotUrl("")).toBe("/api/runtime/warnings/blocking");
  });
  it("strips trailing slashes from cross-origin bases", () => {
    expect(blockingWarningSnapshotUrl("http://localhost:8877/")).toBe(
      "http://localhost:8877/api/runtime/warnings/blocking",
    );
  });
});
