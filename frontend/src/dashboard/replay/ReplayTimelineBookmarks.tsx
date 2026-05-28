/**
 * Bookmark list + jump-to-bookmark control.
 *
 * Renders bookmarks as a vertical list with keyboard navigation
 * support. The bookmark dispatch surface is one ``jump-to-bookmark``
 * intent per activation; the bridge resolves the bookmark id back
 * to a sequence on the engine side.
 */

import type { JSX } from "react";
import {
  describeBookmarkForAccessibility,
} from "@/dashboard/replay/ReplayTimelineAccessibility";
import {
  recordBookmarkAdded,
  recordBookmarkRemoved,
  recordFocusChange,
} from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import {
  recordReplayTimelineTrace,
} from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";
import {
  useReplayBookmarks,
  useReplayFocusedBookmarkId,
  useReplayPlayback,
  useReplayWindow,
} from "@/dashboard/replay/ReplayTimelineSelectors";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import { seekToBookmark } from "@/dashboard/replay/ReplayTimelineSeek";
import type {
  ReplayBookmark,
  ReplayControlIntent,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export interface ReplayTimelineBookmarksProps {
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly onAddBookmark?: () => void;
  readonly className?: string;
}

export function ReplayTimelineBookmarks({
  dispatch,
  onAddBookmark,
  className,
}: ReplayTimelineBookmarksProps): JSX.Element {
  const bookmarks = useReplayBookmarks();
  const focusedId = useReplayFocusedBookmarkId();
  const playback = useReplayPlayback();
  const window = useReplayWindow();
  const setFocused = useReplayTimelineStore((s) => s.setFocusedBookmark);
  const removeBookmark = useReplayTimelineStore((s) => s.removeBookmark);
  const addBookmark = useReplayTimelineStore((s) => s.addBookmark);

  const handleAdd = () => {
    const bookmark: ReplayBookmark = {
      id: `bookmark-${Date.now()}`,
      label: `Bookmark at ${playback.lastSequence}`,
      sequence: playback.lastSequence,
      monotonicNs: playback.lastMonotonicNs,
      createdAtMs: Date.now(),
    };
    addBookmark(bookmark);
    recordBookmarkAdded();
    recordReplayTimelineTrace("bookmark-added", bookmark.id);
    onAddBookmark?.();
  };

  return (
    <section
      aria-label="Replay bookmarks"
      className={"flex flex-col gap-2 " + (className ?? "")}
    >
      <header className="flex items-center justify-between">
        <h2 className="font-mono text-xs uppercase tracking-widest text-textMuted">
          Bookmarks
        </h2>
        <button
          type="button"
          aria-label="Add bookmark at current playhead"
          onClick={handleAdd}
          className="rounded border border-border bg-surface px-2 py-0.5 text-xs text-text"
        >
          + Add
        </button>
      </header>
      <ul role="list" className="flex flex-col gap-1 text-sm text-text">
        {bookmarks.length === 0 && (
          <li className="text-xs text-textMuted">No bookmarks yet.</li>
        )}
        {bookmarks.map((bookmark) => {
          const ariaLabel = describeBookmarkForAccessibility(bookmark, window);
          const focused = bookmark.id === focusedId;
          return (
            <li
              key={bookmark.id}
              aria-label={ariaLabel}
              data-focused={focused || undefined}
              className={
                "flex items-center justify-between rounded border border-border " +
                "bg-surface px-2 py-1 " +
                (focused ? "ring-1 ring-accent" : "")
              }
            >
              <button
                type="button"
                onClick={() => {
                  setFocused(bookmark.id);
                  recordFocusChange();
                  recordReplayTimelineTrace("bookmark-focus", bookmark.id);
                  dispatch(seekToBookmark(bookmark));
                }}
                className="flex-1 text-left"
              >
                <span className="font-mono text-xs text-textMuted">
                  {bookmark.sequence}
                </span>
                <span className="ml-2">{bookmark.label}</span>
              </button>
              <button
                type="button"
                aria-label={`Remove bookmark ${bookmark.label}`}
                onClick={() => {
                  removeBookmark(bookmark.id);
                  recordBookmarkRemoved();
                  recordReplayTimelineTrace("bookmark-removed", bookmark.id);
                }}
                className="ml-2 text-xs text-textMuted hover:text-text"
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
