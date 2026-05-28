import { describe, expect, it } from "vitest";
import { renderWithProviders } from "@/test/render";
import { MetricsSparkline } from "@/dashboard/metrics/components/MetricsSparkline";

describe("MetricsSparkline", () => {
  it("renders an empty fallback when given fewer than 2 samples", () => {
    const { container } = renderWithProviders(<MetricsSparkline samples={[]} />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.querySelector("polyline")).toBeNull();
  });

  it("renders a polyline when given a series", () => {
    const { container } = renderWithProviders(<MetricsSparkline samples={[1, 2, 3, 4]} />);
    expect(container.querySelector("polyline")).not.toBeNull();
  });
});
