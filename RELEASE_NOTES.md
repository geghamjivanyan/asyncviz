# AsyncViz v0.1.0

We are excited to announce the first public release of AsyncViz.

AsyncViz is a real-time visualization and diagnostics tool for Python asyncio applications. It runs alongside your program and provides a live, browser-based view of tasks, queues, semaphores, executors, and await relationships—without requiring changes to your application code.

---

## Highlights

- See every asyncio task, queue, semaphore, executor, and gather in your application as it runs.
- Inspect task lifecycle, parent and child relationships, and per-task warnings as they happen.
- Browse a timeline of task activity to understand when each coroutine runs and how long it takes.
- Visualize `asyncio.gather` fan-outs and await dependencies as a graph.
- Track queue occupancy, throughput, contention, and pressure in real time.
- Track semaphore permits, waiters, and contention.
- Track executor worker utilization, backlog, and saturation.
- View runtime diagnostics that explain detected issues in plain language and suggest possible next steps.
- Read aggregate runtime metrics covering throughput, event rates, and task counts.
- Record a session into a portable `.avz` bundle and replay it later in the same dashboard.
- Use the `asyncviz` command-line tool to run an instrumented script or replay a recorded session.
- Start AsyncViz directly from your code with a single function call, via the public Python API.
- Use the embedded frontend without managing a separate dashboard server.

---

## Getting Started

```python
import asyncviz

asyncviz.start()
```

A complete, runnable example is available under `examples/basic/`.

---

## Documentation

The repository includes:

- `README.md`
- An example project under `examples/basic/`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `CHANGELOG.md`

---

## Feedback

Bug reports, feature requests, suggestions, and contributions are all welcome. The preferred place to start a conversation is [GitHub Issues](https://github.com/geghamjivanyan/asyncviz/issues).

---

## Closing

Thank you for trying the first public release of AsyncViz.

Whether you are reporting bugs, suggesting improvements, or contributing code, your feedback will play an important role in shaping the future of the project.
