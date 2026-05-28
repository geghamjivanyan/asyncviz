import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppErrorBoundary } from "@/app/error/AppErrorBoundary";

function Boom(): JSX.Element {
  throw new Error("kaboom");
}

describe("AppErrorBoundary", () => {
  it("renders children when no error is thrown", () => {
    render(
      <AppErrorBoundary>
        <span>healthy</span>
      </AppErrorBoundary>,
    );
    expect(screen.getByText("healthy")).toBeInTheDocument();
  });

  it("renders the fallback UI when a child raises", () => {
    // React logs the error to the console — silence it for the test.
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    try {
      render(
        <AppErrorBoundary>
          <Boom />
        </AppErrorBoundary>,
      );
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText("kaboom")).toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });

  it("invokes the onError hook with the captured error", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const onError = vi.fn();
    try {
      render(
        <AppErrorBoundary onError={onError}>
          <Boom />
        </AppErrorBoundary>,
      );
      expect(onError).toHaveBeenCalledTimes(1);
      expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(Error);
    } finally {
      consoleError.mockRestore();
    }
  });
});
