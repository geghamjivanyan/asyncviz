import { describe, expect, it } from "vitest";
import { act, render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import {
  DashboardLayoutProvider,
  useDashboardLayout,
} from "@/dashboard/layout/context/DashboardLayoutContext";

function wrapper({ children }: { children: ReactNode }) {
  return <DashboardLayoutProvider>{children}</DashboardLayoutProvider>;
}

describe("DashboardLayoutProvider", () => {
  it("exposes default state via the hook", () => {
    const { result } = renderHook(() => useDashboardLayout(), { wrapper });
    expect(result.current.sidebar).toBe("expanded");
    expect(result.current.fullscreenPanel).toBeNull();
    expect(result.current.statusBarVisible).toBe(true);
    expect(result.current.diagnosticsVisible).toBe(false);
  });

  it("toggles the sidebar between expanded and collapsed", () => {
    const { result } = renderHook(() => useDashboardLayout(), { wrapper });
    act(() => result.current.toggleSidebar());
    expect(result.current.sidebar).toBe("collapsed");
    act(() => result.current.toggleSidebar());
    expect(result.current.sidebar).toBe("expanded");
  });

  it("setFullscreenPanel records the requested id", () => {
    const { result } = renderHook(() => useDashboardLayout(), { wrapper });
    act(() => result.current.setFullscreenPanel("timeline"));
    expect(result.current.fullscreenPanel).toBe("timeline");
    act(() => result.current.setFullscreenPanel(null));
    expect(result.current.fullscreenPanel).toBeNull();
  });

  it("accepts an initialState override", () => {
    const Consumer = () => {
      const { sidebar } = useDashboardLayout();
      return <span>{sidebar}</span>;
    };
    render(
      <DashboardLayoutProvider initialState={{ sidebar: "hidden" }}>
        <Consumer />
      </DashboardLayoutProvider>,
    );
    expect(screen.getByText("hidden")).toBeInTheDocument();
  });

  it("throws when the hook is used outside the provider", () => {
    const original = console.error;
    console.error = () => undefined;
    try {
      expect(() => renderHook(() => useDashboardLayout())).toThrow(/<DashboardLayoutProvider>/);
    } finally {
      console.error = original;
    }
  });
});
