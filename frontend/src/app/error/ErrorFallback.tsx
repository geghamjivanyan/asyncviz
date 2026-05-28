/**
 * Default failure UI rendered by :class:`AppErrorBoundary`.
 *
 * Intentionally minimal — operators in the field need three things:
 * (1) confirmation the dashboard is broken (no blank screen),
 * (2) the error message,
 * (3) a way to retry without a full page reload.
 *
 * Custom error UIs replace this via the ``fallback`` prop on
 * :class:`AppErrorBoundary`.
 */

interface ErrorFallbackProps {
  error: Error;
  reset: () => void;
}

export function ErrorFallback({ error, reset }: ErrorFallbackProps) {
  return (
    <div
      role="alert"
      className="flex h-screen flex-col items-center justify-center gap-4 bg-canvas px-8 text-center text-text"
    >
      <h1 className="font-mono text-lg uppercase tracking-widest text-danger">Dashboard failed</h1>
      <p className="max-w-md font-mono text-sm text-muted">{error.message || String(error)}</p>
      <div className="flex items-center gap-3 text-xs text-subtle">
        <button
          type="button"
          onClick={reset}
          className="rounded border border-line bg-elevated px-3 py-1 text-xs text-text transition-colors hover:border-accent hover:text-accent"
        >
          Retry
        </button>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded border border-line bg-elevated px-3 py-1 text-xs text-text transition-colors hover:border-accent hover:text-accent"
        >
          Reload
        </button>
      </div>
    </div>
  );
}
