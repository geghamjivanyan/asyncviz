/**
 * Metadata panel — surfaces tag + metadata key/value pairs the
 * runtime attached to the task.
 */

import { memo } from "react";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorMetadataProps {
  inspection: TaskInspection;
  className?: string;
}

function TaskInspectorMetadataImpl({ inspection, className }: TaskInspectorMetadataProps) {
  if (inspection.task === null) return null;
  const tags = Object.entries(inspection.task.tags ?? {});
  const metadata = Object.entries(inspection.task.metadata ?? {});
  return (
    <Card
      data-inspector-panel="metadata"
      padding="sm"
      className={cn("flex flex-col gap-2", className)}
    >
      <header>
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Metadata</h3>
      </header>
      {tags.length === 0 && metadata.length === 0 ? (
        <p className="text-[11px] text-subtle">No tags or metadata.</p>
      ) : (
        <>
          {tags.length > 0 ? (
            <section>
              <p className="text-[10px] uppercase tracking-widest text-subtle">Tags</p>
              <ul className="mt-1 flex flex-wrap gap-1 font-mono text-[11px]">
                {tags.map(([key, value]) => (
                  <li
                    key={key}
                    data-tag-key={key}
                    className="rounded border border-line bg-elevated px-1.5 py-0.5"
                  >
                    <span className="text-muted">{key}=</span>
                    <span className="text-text">{value}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {metadata.length > 0 ? (
            <section>
              <p className="text-[10px] uppercase tracking-widest text-subtle">Metadata</p>
              <dl className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-[11px]">
                {metadata.map(([key, value]) => (
                  <Row key={key} label={key} value={renderValue(value)} />
                ))}
              </dl>
            </section>
          ) : null}
        </>
      )}
    </Card>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-[10px] uppercase tracking-widest text-subtle" data-metadata-key={label}>
        {label}
      </dt>
      <dd className="truncate text-text">{value}</dd>
    </>
  );
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export const TaskInspectorMetadata = memo(TaskInspectorMetadataImpl);
