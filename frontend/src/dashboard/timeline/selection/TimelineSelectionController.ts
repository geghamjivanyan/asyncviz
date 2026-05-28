/**
 * Canonical task-row selection controller.
 *
 * The controller is the single chokepoint for every selection
 * mutation. It composes:
 *
 *   * a :type:`SelectionStore` adapter — wraps the runtime store's
 *     ``selectedTaskId`` + ``selectTask`` primitives,
 *   * a row-provider callback — lets the controller resolve "next /
 *     previous / first / last" against the current deterministic row
 *     order without depending on the projection layer,
 *   * an optional ``TimelinePanController`` for center-on-selection,
 *   * an optional ``TimelineZoomController`` for fit-to-selection,
 *   * a :class:`TimelineSelectionMetrics` for observability,
 *   * a subscriber bus that emits :type:`TimelineSelectionState`
 *     snapshots so React rerenders on demand.
 *
 * The controller is framework-free TypeScript so it runs on a worker
 * thread later. React glue lives in
 * :func:`useTimelineSelectionController`.
 */

import type { TaskSnapshot } from "@/types/runtime";
import type { SelectionStore } from "@/dashboard/timeline/selection/TimelineSelectionStore";
import {
  firstTaskId,
  indexOfTask,
  isAtFirst,
  isAtLast,
  lastTaskId,
  nextTaskId,
  previousTaskId,
} from "@/dashboard/timeline/selection/utils/rowNavigation";
import {
  DEFAULT_SELECTION_CONFIG,
  type SelectableRow,
  type SelectionConfig,
  type SelectionReason,
  type TimelineSelectionState,
} from "@/dashboard/timeline/selection/models/TimelineSelectionModels";
import {
  getTimelineSelectionMetrics,
  type TimelineSelectionMetrics,
} from "@/dashboard/timeline/selection/TimelineSelectionMetrics";
import {
  centerWindowOnSelection,
  minimalRevealDelta,
  selectionFullyVisible,
} from "@/dashboard/timeline/selection/TimelineSelectionFocus";
import {
  traceSelectionCenter,
  traceSelectionClear,
  traceSelectionNavigate,
  traceSelectionNoop,
  traceSelectionRestore,
  traceSelectionReveal,
  traceSelectionSelect,
} from "@/dashboard/timeline/selection/TimelineSelectionTracing";

export type SelectionStateListener = (state: TimelineSelectionState) => void;

export interface SelectionRowSource {
  /** Snapshot of the currently selectable rows. */
  getRows(): readonly SelectableRow[];
  /** Resolve a task id → snapshot (or ``null``). */
  getTask(taskId: string | null): TaskSnapshot | null;
  /** Resolve a task id → its time bounds for focus calls. */
  getTaskRange(taskId: string | null): { startSeconds: number; endSeconds: number } | null;
}

export interface SelectionViewportSource {
  /** Get the active viewport in the controller's coordinate space. */
  getViewport(): {
    visibleStartSeconds: number;
    visibleEndSeconds: number;
    durationSeconds: number;
  };
}

export interface SelectionFocusAdapter {
  /** Move the viewport so its left edge sits at ``timeStartSeconds``. */
  panToTimeStart(timeStartSeconds: number): void;
  /** Fit the viewport so it spans ``[startSeconds, endSeconds]``. */
  fitToRange(startSeconds: number, endSeconds: number): void;
}

export interface TimelineSelectionControllerOptions {
  store: SelectionStore;
  rows: SelectionRowSource;
  viewport?: SelectionViewportSource | null;
  focus?: SelectionFocusAdapter | null;
  metrics?: TimelineSelectionMetrics;
  config?: Partial<SelectionConfig>;
}

export class TimelineSelectionController {
  private readonly store: SelectionStore;
  private readonly rows: SelectionRowSource;
  private readonly viewport: SelectionViewportSource | null;
  private readonly focus: SelectionFocusAdapter | null;
  private readonly metrics: TimelineSelectionMetrics;
  private readonly config: SelectionConfig;
  private readonly listeners = new Set<SelectionStateListener>();
  private state: TimelineSelectionState;
  private generation = 0;
  private storeUnsubscribe: (() => void) | null = null;
  private disposed = false;

  constructor(options: TimelineSelectionControllerOptions) {
    this.store = options.store;
    this.rows = options.rows;
    this.viewport = options.viewport ?? null;
    this.focus = options.focus ?? null;
    this.metrics = options.metrics ?? getTimelineSelectionMetrics();
    this.config = { ...DEFAULT_SELECTION_CONFIG, ...(options.config ?? {}) };
    this.state = this.buildState(this.store.getSelectedTaskId(), "restore");
    this.storeUnsubscribe = this.store.subscribe((taskId) => {
      this.refreshState(taskId, "store");
    });
  }

  // ── public surface ───────────────────────────────────────────────

  currentState(): TimelineSelectionState {
    return this.state;
  }

  subscribe(listener: SelectionStateListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Select a row by task id. */
  selectRow(taskId: string | null, reason: SelectionReason = "programmatic"): void {
    if (this.disposed) return;
    if (taskId === this.state.selectedTaskId) {
      this.metrics.recordNoopSuppressed();
      traceSelectionNoop(`already-selected ${taskId ?? "null"}`);
      return;
    }
    const start = nowMs();
    this.store.setSelectedTaskId(taskId);
    this.metrics.recordSelectionChange(reason);
    this.metrics.recordChangeLatency(nowMs() - start);
    traceSelectionSelect(`task=${taskId ?? "null"} reason=${reason}`);
    if (this.config.autoCenter) this.centerOnSelection();
    if (this.config.autoZoomToFit) this.fitToSelection();
  }

  /** Clear the selection. */
  clearSelection(reason: SelectionReason = "clear"): void {
    if (this.disposed) return;
    if (this.state.selectedTaskId === null) {
      this.metrics.recordNoopSuppressed();
      traceSelectionNoop("already-cleared");
      return;
    }
    this.store.setSelectedTaskId(null);
    this.metrics.recordSelectionChange(reason);
    traceSelectionClear(`reason=${reason}`);
  }

  /** Select the next row (wraps optionally). */
  selectNext(options: { wrap?: boolean } = {}): void {
    if (this.disposed) return;
    const target = nextTaskId(this.rows.getRows(), this.state.selectedTaskId, options);
    if (target === null || target === this.state.selectedTaskId) {
      this.metrics.recordNoopSuppressed();
      traceSelectionNoop("next no-op");
      return;
    }
    this.metrics.recordNavigation("next");
    traceSelectionNavigate(`next → ${target}`);
    this.selectRow(target, "keyboard");
  }

  /** Select the previous row (wraps optionally). */
  selectPrevious(options: { wrap?: boolean } = {}): void {
    if (this.disposed) return;
    const target = previousTaskId(this.rows.getRows(), this.state.selectedTaskId, options);
    if (target === null || target === this.state.selectedTaskId) {
      this.metrics.recordNoopSuppressed();
      traceSelectionNoop("previous no-op");
      return;
    }
    this.metrics.recordNavigation("prev");
    traceSelectionNavigate(`previous → ${target}`);
    this.selectRow(target, "keyboard");
  }

  /** Select the first row. */
  selectFirst(): void {
    if (this.disposed) return;
    const target = firstTaskId(this.rows.getRows());
    if (target === null || target === this.state.selectedTaskId) {
      this.metrics.recordNoopSuppressed();
      traceSelectionNoop("first no-op");
      return;
    }
    this.metrics.recordNavigation("home");
    traceSelectionNavigate(`first → ${target}`);
    this.selectRow(target, "keyboard");
  }

  /** Select the last row. */
  selectLast(): void {
    if (this.disposed) return;
    const target = lastTaskId(this.rows.getRows());
    if (target === null || target === this.state.selectedTaskId) {
      this.metrics.recordNoopSuppressed();
      traceSelectionNoop("last no-op");
      return;
    }
    this.metrics.recordNavigation("end");
    traceSelectionNavigate(`last → ${target}`);
    this.selectRow(target, "keyboard");
  }

  /** Center the viewport on the active selection. */
  centerOnSelection(): void {
    if (this.disposed) return;
    if (this.focus === null || this.viewport === null) return;
    const range = this.rows.getTaskRange(this.state.selectedTaskId);
    if (range === null) return;
    const view = this.viewport.getViewport();
    const newStart = centerWindowOnSelection(range, view.durationSeconds);
    this.focus.panToTimeStart(newStart);
    this.metrics.recordCenter();
    traceSelectionCenter(`task=${this.state.selectedTaskId} → start=${newStart}`);
  }

  /** Reveal the selection inside the visible viewport — the cheapest
   *  pan that brings the selection back into view. */
  revealSelection(options: { paddingSeconds?: number } = {}): void {
    if (this.disposed) return;
    if (this.focus === null || this.viewport === null) return;
    const range = this.rows.getTaskRange(this.state.selectedTaskId);
    if (range === null) return;
    const view = this.viewport.getViewport();
    const window = {
      startSeconds: view.visibleStartSeconds,
      endSeconds: view.visibleEndSeconds,
    };
    if (selectionFullyVisible(range, window)) {
      this.metrics.recordNoopSuppressed();
      traceSelectionNoop("reveal already-visible");
      return;
    }
    const delta = minimalRevealDelta(range, window, options);
    if (delta === 0) return;
    this.focus.panToTimeStart(view.visibleStartSeconds + delta);
    this.metrics.recordReveal();
    traceSelectionReveal(`delta=${delta} task=${this.state.selectedTaskId}`);
  }

  /** Fit the viewport to the selection's time range. */
  fitToSelection(): void {
    if (this.disposed) return;
    if (this.focus === null) return;
    const range = this.rows.getTaskRange(this.state.selectedTaskId);
    if (range === null) return;
    if (!(range.endSeconds > range.startSeconds)) return;
    this.focus.fitToRange(range.startSeconds, range.endSeconds);
    traceSelectionReveal(`fit task=${this.state.selectedTaskId}`);
  }

  /** Restore a persisted selection — used after replay batches +
   *  page reloads. */
  restoreSelection(taskId: string | null): void {
    if (this.disposed) return;
    const rows = this.rows.getRows();
    const hit = taskId !== null && indexOfTask(rows, taskId) >= 0;
    this.metrics.recordRestore(hit);
    traceSelectionRestore(`task=${taskId ?? "null"} hit=${hit}`);
    if (!hit) {
      if (this.state.selectedTaskId !== null) this.clearSelection("restore");
      return;
    }
    if (taskId === this.state.selectedTaskId) return;
    this.store.setSelectedTaskId(taskId);
    this.metrics.recordSelectionChange("restore");
  }

  /** Re-derive state — called after row-projection changes. */
  refresh(): void {
    this.refreshState(this.store.getSelectedTaskId(), this.state.lastReason ?? "store");
  }

  metricsSnapshot() {
    return this.metrics.snapshot();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.storeUnsubscribe?.();
    this.storeUnsubscribe = null;
    this.listeners.clear();
  }

  // ── internals ────────────────────────────────────────────────────

  private buildState(
    selectedTaskId: string | null,
    reason: SelectionReason,
  ): TimelineSelectionState {
    const rows = this.rows.getRows();
    const selectedRowIndex = indexOfTask(rows, selectedTaskId);
    const selectedTask = this.rows.getTask(selectedTaskId);
    this.generation += 1;
    return {
      selectedTaskId,
      selectedRowIndex,
      selectedTask,
      rowCount: rows.length,
      atFirst: isAtFirst(rows, selectedTaskId),
      atLast: isAtLast(rows, selectedTaskId),
      lastReason: reason,
      generation: this.generation,
    };
  }

  private refreshState(selectedTaskId: string | null, reason: SelectionReason): void {
    const next = this.buildState(selectedTaskId, reason);
    this.state = next;
    for (const listener of this.listeners) {
      try {
        listener(next);
      } catch (err) {
        console.error("TimelineSelectionController: listener threw", err);
      }
    }
  }
}

function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}
