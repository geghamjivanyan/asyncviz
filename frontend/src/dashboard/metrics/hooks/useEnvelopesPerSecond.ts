/**
 * Tracks rolling envelopes-per-second.
 *
 * The store keeps a cumulative ``envelopesApplied`` counter; the hook
 * samples it at a steady cadence and folds samples into a rate
 * tracker. Returns a number (not a hook tuple) so cards can drop it
 * straight into rendering.
 *
 * The cadence is intentionally 1Hz — sub-second resolution is wasted
 * for a human-visible card.
 */

import { useEffect, useRef, useState } from "react";
import { useRuntimeStore } from "@/state/runtime";
import {
  createRateTracker,
  rateFromTracker,
  recordRateSample,
  type RateTrackerState,
} from "@/dashboard/metrics/models/rateTracker";
import { getMetricsHeaderMetrics } from "@/dashboard/metrics/observability";

const SAMPLE_MS = 1000;

export function useEnvelopesPerSecond(): number {
  const trackerRef = useRef<RateTrackerState>(createRateTracker());
  const [rate, setRate] = useState(0);

  useEffect(() => {
    const handle = window.setInterval(() => {
      const total = useRuntimeStore.getState().stats.envelopesApplied;
      const now = typeof performance !== "undefined" ? performance.now() : Date.now();
      trackerRef.current = recordRateSample(trackerRef.current, total, now);
      getMetricsHeaderMetrics().recordThroughputSample();
      setRate(rateFromTracker(trackerRef.current, now));
    }, SAMPLE_MS);
    return () => window.clearInterval(handle);
  }, []);

  return rate;
}
