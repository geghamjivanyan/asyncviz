/**
 * Top-level error boundary.
 *
 * Catches render errors anywhere below it and switches to the
 * fallback UI. ``reset`` lets users retry without a full page
 * reload — useful when the error was a transient hydration mismatch
 * or a one-shot rendering bug.
 */

import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { ErrorFallback } from "@/app/error/ErrorFallback";

interface AppErrorBoundaryProps {
  /** Custom fallback. Defaults to :class:`ErrorFallback`. */
  fallback?: (props: { error: Error; reset: () => void }) => ReactNode;
  /** Test hook — called when a render error is caught. */
  onError?: (error: Error, info: ErrorInfo) => void;
  children: ReactNode;
}

interface AppErrorBoundaryState {
  error: Error | null;
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.props.onError?.(error, info);
    // Surface the error via the console so frontend telemetry (Sentry,
    // browser DevTools, future :func:`ClientMetrics` integration) can
    // pick it up. Kept narrow on purpose — silence is the worst
    // failure mode.
    console.error("AppErrorBoundary caught", error, info);
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (error !== null) {
      const fallback = this.props.fallback ?? ErrorFallback;
      return fallback({ error, reset: this.reset });
    }
    return this.props.children;
  }
}
