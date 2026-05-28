/**
 * End-to-end wiring test: selecting a card in the
 * BlockingWarningsContainer must mirror into the freeze-region store.
 *
 * This is the canonical cross-link the timeline relies on to flash
 * the matching freeze when the panel selection changes.
 */

import { beforeEach, describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { BlockingWarningsContainer } from "@/dashboard/warnings/blocking";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking";
import { useFreezeRegionStore } from "@/dashboard/timeline/freeze_regions";
import {
  makeSnapshot,
  makeGroup,
} from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";
import { resetBlockingWarningPanelMetrics } from "@/dashboard/warnings/blocking";
import { resetFreezeRegionMetrics } from "@/dashboard/timeline/freeze_regions";

beforeEach(() => {
  useBlockingWarningStore.getState().reset();
  useFreezeRegionStore.getState().reset();
  resetBlockingWarningPanelMetrics();
  resetFreezeRegionMetrics();
});

describe("BlockingWarningsContainer ↔ FreezeRegionStore cross-link", () => {
  it("mirrors the selected card into the freeze-region store and reveals it", async () => {
    const user = userEvent.setup();
    useBlockingWarningStore.getState().hydrateSnapshot(
      makeSnapshot({
        active_groups: [makeGroup({ group_id: "g-active" })],
        recent_groups: [],
      }),
    );
    renderWithProviders(
      <BlockingWarningsContainer disableHydration disableLiveUpdates />,
    );
    await user.click(
      screen.getByTestId("blocking-warning-card-toggle-g-active"),
    );
    expect(useFreezeRegionStore.getState().selectedGroupId).toBe("g-active");
    expect(useFreezeRegionStore.getState().revealedGroupId).toBe("g-active");
  });

  it("clears the freeze reveal when the card is unselected", async () => {
    const user = userEvent.setup();
    useBlockingWarningStore.getState().hydrateSnapshot(
      makeSnapshot({
        active_groups: [makeGroup({ group_id: "g-active" })],
        recent_groups: [],
      }),
    );
    renderWithProviders(
      <BlockingWarningsContainer disableHydration disableLiveUpdates />,
    );
    const toggle = screen.getByTestId("blocking-warning-card-toggle-g-active");
    await user.click(toggle);
    await user.click(toggle);
    expect(useFreezeRegionStore.getState().selectedGroupId).toBeNull();
    expect(useFreezeRegionStore.getState().revealedGroupId).toBeNull();
  });
});
