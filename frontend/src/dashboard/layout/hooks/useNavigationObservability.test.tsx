import { describe, expect, it } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Link } from "react-router-dom";
import { AppProviders } from "@/app/providers/AppProviders";
import { createTestConfig } from "@/app/configuration/runtimeConfig";
import { ClientMetrics } from "@/runtime/observability/clientMetrics";
import { RuntimeProvider, useClientMetrics } from "@/app/providers/RuntimeProvider";
import { ConfigProvider } from "@/app/providers/ConfigProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import { useNavigationObservability } from "@/dashboard/layout/hooks/useNavigationObservability";

function ProbeRoutes() {
  useNavigationObservability();
  return (
    <>
      <Link to="/timeline">to-timeline</Link>
      <Routes>
        <Route path="/" element={<span>home</span>} />
        <Route path="/timeline" element={<span>timeline</span>} />
      </Routes>
    </>
  );
}

function MetricsReadout() {
  const metrics = useClientMetrics();
  return <span data-testid="nav-total">{metrics.snapshot().navigationsTotal}</span>;
}

describe("useNavigationObservability", () => {
  it("records one navigation per distinct pathname", async () => {
    const metrics = new ClientMetrics();
    const config = createTestConfig();
    render(
      <ConfigProvider config={config}>
        <ThemeProvider>
          <RuntimeProvider metrics={metrics}>
            <MemoryRouter initialEntries={["/"]}>
              <ProbeRoutes />
              <MetricsReadout />
            </MemoryRouter>
          </RuntimeProvider>
        </ThemeProvider>
      </ConfigProvider>,
    );
    // Mount records the initial path.
    expect(metrics.snapshot().navigationsTotal).toBe(1);
    // Click the link to navigate.
    await act(async () => {
      screen.getByText("to-timeline").click();
    });
    expect(metrics.snapshot().navigationsTotal).toBe(2);
  });

  it("does not double-count when the same path re-renders", () => {
    const metrics = new ClientMetrics();
    const ui = (
      <AppProviders config={createTestConfig()}>
        <RuntimeProvider metrics={metrics}>
          <MemoryRouter initialEntries={["/"]}>
            <ProbeRoutes />
          </MemoryRouter>
        </RuntimeProvider>
      </AppProviders>
    );
    const { rerender } = render(ui);
    rerender(ui);
    rerender(ui);
    expect(metrics.snapshot().navigationsTotal).toBe(1);
  });
});
