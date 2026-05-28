/**
 * Tiny sparkline.
 *
 * Foundational — accepts a normalized sample array and renders a
 * polyline inside an SVG. The architecture is sufficient to support
 * a real history series (1-second buckets, multi-stream blends)
 * without a re-design.
 *
 * The component is decorative — screen readers see the parent card's
 * label, not the sparkline shape. ``aria-hidden`` makes that explicit.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";

export interface MetricsSparklineProps {
  /** Sample series in observation order; arbitrary scale. */
  samples: readonly number[];
  /** Render width in px. */
  width?: number;
  /** Render height in px. */
  height?: number;
  className?: string;
  /** Stroke color (Tailwind class name). */
  strokeClass?: string;
}

function MetricsSparklineImpl({
  samples,
  width = 60,
  height = 16,
  className,
  strokeClass = "stroke-accent",
}: MetricsSparklineProps) {
  if (samples.length < 2) {
    return (
      <svg
        aria-hidden="true"
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={cn("opacity-50", className)}
      >
        <line
          x1={0}
          x2={width}
          y1={height / 2}
          y2={height / 2}
          className={cn("stroke-line", strokeClass)}
          strokeWidth={1}
        />
      </svg>
    );
  }
  const min = Math.min(...samples);
  const max = Math.max(...samples);
  const range = max - min;
  const stepX = width / (samples.length - 1);
  const points = samples
    .map((value, index) => {
      const ratio = range === 0 ? 0.5 : (value - min) / range;
      const x = index * stepX;
      const y = height - ratio * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      aria-hidden="true"
      data-metrics-sparkline="true"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      preserveAspectRatio="none"
    >
      <polyline
        fill="none"
        className={strokeClass}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points}
      />
    </svg>
  );
}

export const MetricsSparkline = memo(MetricsSparklineImpl);
