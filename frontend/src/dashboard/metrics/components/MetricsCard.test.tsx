/**
 * Component tests for :class:`MetricsCard`.
 */

import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";

describe("MetricsCard", () => {
  it("renders label + value", () => {
    renderWithProviders(<MetricsCard id="x" label="Tasks" value="42" />);
    expect(screen.getByText("Tasks")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders a placeholder when loading", () => {
    renderWithProviders(<MetricsCard id="x" label="Tasks" loading value="42" />);
    expect(screen.getByText("…")).toBeInTheDocument();
  });

  it("uses accessible role + label", () => {
    renderWithProviders(<MetricsCard id="health" label="Health" value="ok" />);
    expect(screen.getByRole("group", { name: /Health/i })).toBeInTheDocument();
  });

  it("renders error state attribute", () => {
    renderWithProviders(<MetricsCard id="x" label="Tasks" errored value="—" />);
    const card = screen.getByRole("group", { name: /Tasks/i });
    expect(card).toHaveAttribute("data-error", "true");
  });
});
