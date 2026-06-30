# AsyncViz · basic example

The smallest end-to-end AsyncViz workload. Use this as a starting
point for your own integration.

## How to run

From this directory, with AsyncViz already installed:

```bash
python app.py
```

`app.py` calls `asyncviz.start()`, which serves the dashboard at
<http://127.0.0.1:8877> and opens your default browser to it. The
script then runs a small asyncio workload (heartbeat, producer,
two workers behind a bounded queue, a parent task that gathers a
fan-out of children, and four workers competing for a shared
semaphore) so every dashboard page has something to show right
away.

## Expected dashboard

Once the page loads you should see:

- **Tasks** — every coroutine listed (`heartbeat`, `producer`,
  `worker-1`, `worker-2`, `parent`, `sem-worker-1` … `sem-worker-4`,
  plus the children spawned by `asyncio.gather`)
- **Timeline** — bars for each task lighting up as they run
- **Queues** — the bounded queue's occupancy oscillating during
  producer bursts
- **Semaphores** — the shared semaphore showing brief, healthy
  contention as the four `sem-worker` tasks compete for two permits
- **Dependencies** — the parent → children fan-out from
  `asyncio.gather(...)`
- **Metrics** — task counts, throughput, and event rate
- **Replay** — playback-ready; once you have a recording you can
  scrub the same event stream
- **Diagnostics** — health, recommendations, and the runtime
  summary

## How to stop

Press **Ctrl+C** in the terminal where `app.py` is running. The
script cancels every task, calls `asyncviz.stop()`, and exits
cleanly.
