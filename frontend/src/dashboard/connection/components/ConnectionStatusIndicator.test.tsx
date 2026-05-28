/**
 * Integration tests for the connection-status indicator.
 *
 * Mount :class:`ConnectionStatusContainer` against the canonical
 * provider stack, mutate the store, and assert that the indicator
 * reflects the change.
 */

import { describe, expect, it, beforeEach } from "vitest";
import { act } from "react";
import { fireEvent, screen, within } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { useRuntimeStore } from "@/state/runtime/store";
import { ConnectionStatusContainer } from "@/dashboard/connection/components/ConnectionStatusContainer";
import { getConnectionMetrics, resetConnectionMetrics } from "@/dashboard/connection/observability";

describe("ConnectionStatusContainer", () => {
  beforeEach(() => {
    resetConnectionMetrics();
    useRuntimeStore.getState().reset();
  });

  it("renders the canonical badge against the live store", () => {
    renderWithProviders(<ConnectionStatusContainer />);
    const indicator = document.querySelector("[data-connection-indicator]");
    expect(indicator).not.toBeNull();
  });

  it("reflects the phase via data attribute + accessible label", () => {
    renderWithProviders(<ConnectionStatusContainer />);
    act(() => {
      useRuntimeStore.getState().setConnectionPhase("live", 0);
    });
    const indicator = document.querySelector("[data-connection-indicator]")!;
    expect(indicator.getAttribute("data-connection-phase")).toBe("live");
    expect(within(indicator as HTMLElement).getByText(/Live/i)).toBeInTheDocument();
  });

  it("renders 'Reconnecting' label when phase is reconnecting", () => {
    renderWithProviders(<ConnectionStatusContainer />);
    act(() => {
      useRuntimeStore.getState().setConnectionPhase("reconnecting", 2);
    });
    const indicator = document.querySelector("[data-connection-indicator]")!;
    expect(indicator.getAttribute("data-connection-phase")).toBe("reconnecting");
    expect(within(indicator as HTMLElement).getByText(/Reconnecting/i)).toBeInTheDocument();
  });

  it("toggles the tooltip on the disclosure button", () => {
    renderWithProviders(<ConnectionStatusContainer />);
    const toggle = screen.getByRole("button", { name: /Show connection details/i });
    fireEvent.click(toggle);
    expect(screen.getByRole("group", { name: /Connection/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Hide connection details/i }));
    expect(screen.queryByRole("group", { name: /Connection/i })).toBeNull();
  });

  it("renders the badge-only variant when requested", () => {
    renderWithProviders(<ConnectionStatusContainer badgeOnly />);
    expect(document.querySelector("[data-connection-indicator]")).toBeNull();
    // The bare badge still carries the phase data attribute.
    expect(document.querySelector("[data-connection-phase]")).not.toBeNull();
  });

  it("increments observability counters on render", () => {
    renderWithProviders(<ConnectionStatusContainer />);
    const snap = getConnectionMetrics().snapshot();
    expect(snap.projectionRebuilds).toBeGreaterThan(0);
    expect(snap.indicatorRenders).toBeGreaterThan(0);
  });

  it("surfaces the reconnect-attempts badge inside the tooltip", () => {
    renderWithProviders(<ConnectionStatusContainer />);
    act(() => {
      useRuntimeStore.getState().setConnectionPhase("reconnecting", 4);
    });
    fireEvent.click(screen.getByRole("button", { name: /Show connection details/i }));
    expect(screen.getByText(/retry 4/i)).toBeInTheDocument();
  });

  it("surfaces a cold-restart label when the replay window is missed", () => {
    renderWithProviders(<ConnectionStatusContainer />);
    act(() => {
      useRuntimeStore.setState({
        replay: { oldestRetainedSequence: null, newestRetainedSequence: null, windowHit: false },
      });
    });
    fireEvent.click(screen.getByRole("button", { name: /Show connection details/i }));
    expect(screen.getByText(/cold/i)).toBeInTheDocument();
  });
});
