import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TimelinePanToolbar } from "@/dashboard/timeline/pan/TimelinePanToolbar";
import { TimelinePanController } from "@/dashboard/timeline/pan/TimelinePanController";
import { buildEngine } from "@/dashboard/timeline/pan/__fixtures__/makePanFixtures";

describe("TimelinePanToolbar", () => {
  it("renders a placeholder when controller is null", () => {
    render(<TimelinePanToolbar controller={null} state={null} />);
    expect(screen.getByText(/Pan controls unavailable/)).toBeInTheDocument();
  });

  it("renders left + right buttons", () => {
    const engine = buildEngine();
    const controller = new TimelinePanController({ engine });
    render(
      <TimelinePanToolbar
        controller={controller}
        state={controller.currentState()}
      />,
    );
    expect(screen.getByLabelText("Pan left")).toBeInTheDocument();
    expect(screen.getByLabelText("Pan right")).toBeInTheDocument();
  });

  it("renders Home + End when a dataRange is supplied", () => {
    const engine = buildEngine();
    const controller = new TimelinePanController({ engine });
    render(
      <TimelinePanToolbar
        controller={controller}
        state={controller.currentState()}
        dataRange={{ startSeconds: 0, endSeconds: 100 }}
      />,
    );
    expect(screen.getByLabelText("Pan to start")).toBeInTheDocument();
    expect(screen.getByLabelText("Pan to end")).toBeInTheDocument();
  });

  it("clicking ▶ pans the controller right", async () => {
    const engine = buildEngine();
    const controller = new TimelinePanController({ engine });
    const user = userEvent.setup();
    render(
      <TimelinePanToolbar
        controller={controller}
        state={controller.currentState()}
      />,
    );
    const before = engine.currentScale().timeStart;
    await user.click(screen.getByLabelText("Pan right"));
    expect(engine.currentScale().timeStart).toBeGreaterThan(before);
  });

  it("disables ◀ when atMinTime", () => {
    const engine = buildEngine();
    const controller = new TimelinePanController({
      engine,
      bounds: { minTimeSeconds: 0, maxTimeSeconds: 100 },
    });
    render(
      <TimelinePanToolbar
        controller={controller}
        state={controller.currentState()}
      />,
    );
    expect(screen.getByLabelText("Pan left")).toBeDisabled();
  });
});
