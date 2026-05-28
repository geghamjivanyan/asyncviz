import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { ConnectionHistory } from "@/dashboard/connection/components/ConnectionHistory";
import type { ConnectionHistoryEntry } from "@/dashboard/connection/models/state";

function entry(overrides: Partial<ConnectionHistoryEntry> = {}): ConnectionHistoryEntry {
  return {
    atMonotonicMs: 100,
    atWallMs: 1000,
    kind: "phase_changed",
    phase: "live",
    sequence: 1,
    reconnectAttempts: 0,
    detail: "test",
    ...overrides,
  };
}

describe("ConnectionHistory", () => {
  it("renders empty hint when no entries", () => {
    renderWithProviders(<ConnectionHistory entries={[]} />);
    expect(screen.getByText(/No transitions recorded yet/i)).toBeInTheDocument();
  });

  it("renders each entry's kind + detail", () => {
    renderWithProviders(
      <ConnectionHistory
        entries={[
          entry({ kind: "phase_changed", detail: "live → reconnecting" }),
          entry({ kind: "reconnect_attempted", detail: "Attempt #1" }),
        ]}
      />,
    );
    expect(screen.getByText("live → reconnecting")).toBeInTheDocument();
    expect(screen.getByText("Attempt #1")).toBeInTheDocument();
  });

  it("invokes onClear from the toolbar", () => {
    const onClear = vi.fn();
    renderWithProviders(<ConnectionHistory entries={[entry()]} onClear={onClear} />);
    fireEvent.click(screen.getByRole("button", { name: /Clear/i }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
