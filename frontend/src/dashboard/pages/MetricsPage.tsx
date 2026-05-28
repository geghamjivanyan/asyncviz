import { EmptyState } from "@/ui/feedback/EmptyState";

export function MetricsPage() {
  return (
    <EmptyState
      title="Metrics"
      description="Aggregate runtime metrics + histograms. Backed by /api/runtime/aggregate."
    />
  );
}
