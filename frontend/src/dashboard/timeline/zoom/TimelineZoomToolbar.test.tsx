import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TimelineZoomToolbar } from "@/dashboard/timeline/zoom/TimelineZoomToolbar";
import { TimelineZoomController } from "@/dashboard/timeline/zoom/TimelineZoomController";
import { buildEngine } from "@/dashboard/timeline/zoom/__fixtures__/makeZoomFixtures";

describe("TimelineZoomToolbar", () => {
  it("renders a placeholder when controller is null", () => {
    render(<TimelineZoomToolbar controller={null} state={null} />);
    expect(screen.getByText(/Zoom controls unavailable/)).toBeInTheDocument();
  });

  it("renders +/-/Fit/Reset when controller is present", () => {
    const engine = buildEngine();
    const controller = new TimelineZoomController({ engine });
    render(
      <TimelineZoomToolbar
        controller={controller}
        state={controller.currentState()}
        fitAll={{ startSeconds: 0, endSeconds: 5 }}
      />,
    );
    expect(screen.getByLabelText("Zoom in")).toBeInTheDocument();
    expect(screen.getByLabelText("Zoom out")).toBeInTheDocument();
    expect(screen.getByLabelText("Fit timeline to data")).toBeInTheDocument();
    expect(screen.getByLabelText("Reset zoom")).toBeInTheDocument();
  });

  it("clicking + zooms in via the controller", async () => {
    const engine = buildEngine();
    const controller = new TimelineZoomController({ engine });
    const user = userEvent.setup();
    render(
      <TimelineZoomToolbar
        controller={controller}
        state={controller.currentState()}
        fitAll={{ startSeconds: 0, endSeconds: 10 }}
      />,
    );
    const before = engine.currentScale().durationSeconds;
    await user.click(screen.getByLabelText("Zoom in"));
    expect(engine.currentScale().durationSeconds).toBeLessThan(before);
  });

  it("clicking Fit jumps to the supplied range", async () => {
    const engine = buildEngine();
    const controller = new TimelineZoomController({ engine });
    const user = userEvent.setup();
    render(
      <TimelineZoomToolbar
        controller={controller}
        state={controller.currentState()}
        fitAll={{ startSeconds: 1, endSeconds: 3 }}
      />,
    );
    await user.click(screen.getByLabelText("Fit timeline to data"));
    expect(engine.currentScale().timeStart).toBe(1);
    expect(engine.currentScale().timeEnd).toBe(3);
  });

  it("disables + when the controller is at the min", () => {
    const engine = buildEngine({ minDurationSeconds: 10, maxDurationSeconds: 100 });
    const controller = new TimelineZoomController({ engine });
    // Force the engine to its min via the controller.
    controller.zoomBy(0.01);
    render(
      <TimelineZoomToolbar
        controller={controller}
        state={controller.currentState()}
        fitAll={{ startSeconds: 0, endSeconds: 10 }}
      />,
    );
    expect(screen.getByLabelText("Zoom in")).toBeDisabled();
  });
});
