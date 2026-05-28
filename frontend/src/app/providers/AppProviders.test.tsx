import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { useRuntimeConfig } from "@/app/providers/ConfigProvider";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useClientMetrics, useWebSocketClient } from "@/app/providers/RuntimeProvider";
import { renderWithProviders } from "@/test/render";

function ConfigConsumer() {
  const config = useRuntimeConfig();
  return <div data-testid="config-protocol">{config.protocolVersion}</div>;
}

function ThemeConsumer() {
  const { theme } = useTheme();
  return <div data-testid="theme-current">{theme}</div>;
}

function RuntimeConsumer() {
  const client = useWebSocketClient();
  const metrics = useClientMetrics();
  return (
    <div>
      <div data-testid="has-client">{client ? "yes" : "no"}</div>
      <div data-testid="has-metrics">{metrics ? "yes" : "no"}</div>
    </div>
  );
}

describe("AppProviders", () => {
  it("exposes the config through the ConfigProvider context", () => {
    renderWithProviders(<ConfigConsumer />);
    expect(screen.getByTestId("config-protocol")).toHaveTextContent("1.0");
  });

  it("defaults to dark theme", () => {
    renderWithProviders(<ThemeConsumer />);
    expect(screen.getByTestId("theme-current")).toHaveTextContent("dark");
  });

  it("constructs a websocket client + metrics instance via RuntimeProvider", () => {
    renderWithProviders(<RuntimeConsumer />);
    expect(screen.getByTestId("has-client")).toHaveTextContent("yes");
    expect(screen.getByTestId("has-metrics")).toHaveTextContent("yes");
  });

  it("sets the data-theme attribute on documentElement", () => {
    renderWithProviders(<ThemeConsumer />);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
