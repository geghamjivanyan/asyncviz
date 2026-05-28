/**
 * Tests for :class:`DashboardPanel` + its subcomponents.
 */

import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import {
  DashboardPanel,
  PanelBody,
  PanelHeader,
  PanelStatusBadge,
  PanelToolbar,
} from "@/dashboard/layout/DashboardPanel";

describe("DashboardPanel", () => {
  it("renders title + body + toolbar", () => {
    renderWithProviders(
      <DashboardPanel id="example">
        <PanelHeader title="Example" subtitle="subtitle">
          <PanelToolbar>
            <PanelStatusBadge intent="success">live</PanelStatusBadge>
          </PanelToolbar>
        </PanelHeader>
        <PanelBody>panel content</PanelBody>
      </DashboardPanel>,
    );
    expect(screen.getByText("Example")).toBeInTheDocument();
    expect(screen.getByText("subtitle")).toBeInTheDocument();
    expect(screen.getByText("live")).toBeInTheDocument();
    expect(screen.getByText("panel content")).toBeInTheDocument();
  });

  it("stamps the panel id + loading/error state on the root", () => {
    renderWithProviders(
      <DashboardPanel id="my-panel" loading error={new Error("boom")}>
        <PanelHeader title="Errored" />
        <PanelBody>body</PanelBody>
      </DashboardPanel>,
    );
    const root = screen.getByRole("group", { name: /my-panel/i });
    expect(root).toHaveAttribute("data-panel-id", "my-panel");
    expect(root).toHaveAttribute("data-panel-loading", "true");
    expect(root).toHaveAttribute("data-panel-error", "true");
  });

  it("PanelBody is labeled with the panel id for accessibility", () => {
    renderWithProviders(
      <DashboardPanel id="labeled">
        <PanelHeader title="Labeled" />
        <PanelBody>x</PanelBody>
      </DashboardPanel>,
    );
    expect(screen.getByRole("region", { name: /labeled body/i })).toBeInTheDocument();
  });

  it("PanelBody throws when used outside a DashboardPanel", () => {
    // React's render call throws synchronously. Silence the noisy console
    // React prints for caught render errors so the test output stays clean.
    const original = console.error;
    console.error = () => undefined;
    try {
      expect(() => renderWithProviders(<PanelBody>orphan</PanelBody>)).toThrow(
        /inside <DashboardPanel>/,
      );
    } finally {
      console.error = original;
    }
  });
});
