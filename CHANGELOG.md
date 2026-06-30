# Changelog

This project follows [Keep a Changelog](https://keepachangelog.com/) and adheres to [Semantic Versioning](https://semver.org/).

---

## [0.1.0] - Initial Release

### Added

- Asyncio runtime instrumentation that observes tasks, queues, semaphores, executors, and `asyncio.gather` activity without requiring changes to user code.
- Interactive web dashboard served from the embedded application, providing a single place to inspect a running asyncio runtime.
- Live task inspection, including lifecycle state, parent and child relationships, and per-task warnings.
- Timeline visualization showing task activity over time.
- Dependency graph visualization for `asyncio.gather` fan-outs and await topology.
- Queue inspection with occupancy, throughput, contention, and pressure indicators.
- Semaphore inspection with permit usage, waiters, and contention indicators.
- Executor inspection with worker utilization, backlog, and saturation indicators.
- Runtime diagnostics center that summarizes findings, recommendations, and per-subsystem health in plain language.
- Runtime metrics including throughput, event rates, task counts, and aggregate runtime statistics.
- Recording support that captures runtime activity into a portable `.avz` bundle.
- Replay support for inspecting captured sessions in the dashboard, including a lane-based timeline, minimap, scrubber, bookmarks, and selection statistics.
- Command-line interface (`asyncviz`) for running an instrumented script and replaying a recorded bundle.
- Embedded frontend served from the AsyncViz package, removing the need for a separate frontend process in production use.
- Public Python API exposed at the package root, including `asyncviz.start()`, `asyncviz.stop()`, `asyncviz.is_running()`, and `asyncviz.get_runtime()`.
- Example project under `examples/basic/` demonstrating the minimal code required to start AsyncViz and exercise the dashboard.
- Project documentation, including `README.md`, `CONTRIBUTING.md`, and `CODE_OF_CONDUCT.md`.
- Screenshots and a demo GIF under `docs/images/` for use in the README and on PyPI.

---

### Notes

This is the first public release of AsyncViz.

Future releases will continue to expand functionality while refining the dashboard and broadening runtime coverage. Feedback, bug reports, and contributions from early users are greatly appreciated.
