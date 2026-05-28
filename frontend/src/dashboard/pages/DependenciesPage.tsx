/**
 * Await dependency graph page.
 *
 * Renders the layered DAG visualization of every gather call observed
 * so far. The container owns the websocket bridge + projection;
 * here we just frame the page.
 */

import { AwaitDependencyGraphContainer } from "@/dashboard/dependencies/AwaitDependencyGraphContainer";

export function DependenciesPage(): JSX.Element {
  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6 text-sm text-text">
      <header className="flex items-center justify-between gap-4">
        <h1 className="font-mono text-base uppercase tracking-widest text-text">
          Await dependencies
        </h1>
      </header>

      <AwaitDependencyGraphContainer />
    </div>
  );
}
