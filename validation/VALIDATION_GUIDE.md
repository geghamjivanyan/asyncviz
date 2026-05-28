# AsyncViz validation guide

Six focused runtime scripts that intentionally over-trigger one
instrumentation subsystem each, plus a `mega_runtime` that runs
scaled-down versions of all of them in parallel. Use these to verify
end-to-end that every dashboard surface lights up under the kind of
backend traffic it was designed for.

> These are **validation** workloads, not example applications. They
> deliberately produce unrealistic amounts of contention, blocking,
> and cancellation. That's the point — instrumentation coverage is
> what's being checked, not user-facing behavior.

---

## Common operating model

Every runtime accepts the same baseline flags (in addition to its
own subsystem-specific knobs):

| Flag | Default | Meaning |
|---|---|---|
| `--duration <s>` | `90.0` | seconds to run before graceful shutdown |
| `--seed <int>` | `1` | seed for randomized timings (deterministic re-runs) |
| `--log-level {DEBUG,INFO,WARNING,ERROR}` | `INFO` | root logger level |

All scripts handle `SIGINT` / `SIGTERM`: the workload signals every
spawned task to stop, awaits cancellation, swallows the expected
`CancelledError`, and exits 0. A run interrupted at `t=10s` looks
the same as one that finished its `--duration` cleanly.

### Launching with the dashboard attached

```bash
# Through the canonical CLI:
asyncviz run validation/<runtime>.py

# Or through the helper script:
python validation/run_validation.py <name>

# Forward args to the runtime past a `--` separator:
python validation/run_validation.py queue -- --duration 60
```

The helper script names map to filenames as follows: `blocking`,
`gather`, `queue`, `executor`, `semaphore`, `mega`. Run
`python validation/run_validation.py --list` for the index.

To suppress the auto-open browser (useful in headless terminals):

```bash
ASYNCVIZ_OPEN_BROWSER=false asyncviz run validation/mega_runtime.py
```

### Launching without the dashboard

Useful for verifying a runtime is well-formed before bringing the
backend up:

```bash
python validation/blocking_runtime.py --duration 5
# or via the helper:
python validation/run_validation.py blocking --no-asyncviz -- --duration 5
```

The runtime imports cleanly, runs its workload, and exits 0. No
dashboard, no instrumentation — just the asyncio behavior.

---

## 1. `blocking_runtime.py`

**Validates**

- Event-loop lag sampler (`asyncio.loop.blocked`).
- Blocking-threshold detector (warning + critical buckets).
- Stack-capture engine (which frame the freeze is attributed to).
- Warning-emitter group lifecycle (opened → escalating → active →
  recovered → expired) and per-group stack attachment.

**Run**

```bash
asyncviz run validation/blocking_runtime.py
# or: python validation/run_validation.py blocking
```

**What you should see in the dashboard**

| Page | Expected | Why |
|---|---|---|
| **Warnings** | Multiple warning groups appear within ~10–15s. At least one CRITICAL group with a captured stack pointing at `heavy_offender` or `_inner_compute`. Groups transition through escalating → active → recovered as offenders pause between blocks. | The four offender tasks land in different severity buckets. |
| **Timeline** | Horizontal "freeze" bars in the timeline aligned with each block. The bars stack visibly on the y-axis when multiple offenders run concurrently. | The lag monitor emits `asyncio.loop.blocked` events with `started_at`/`duration` ranges that the timeline renderer projects as blocks. |
| **Tasks** | 5 long-running tasks: `keepalive-chatter`, `rapid-offender`, `heavy-offender`, `burst-offender`, `nested-offender`. Each in RUNNING state. | They are the actual `asyncio.create_task` rows. |
| **Diagnostics** | Lag p99 spikes coinciding with `heavy_offender` and `burst_offender` cycles. | Lag samples are folded into the latency histogram. |

**Success criteria**

- Within the first 15 seconds of run time, at least one warning
  group is in the **critical** severity bucket on the Warnings page,
  with a stack trace pointing at one of `heavy_offender`,
  `burst_offender`, or `nested_offender → _middle → _inner_compute`.
- The Warnings page shows distinct groups for the rapid (warning),
  heavy (critical), burst (escalating), and nested (critical)
  offenders — not a single coalesced group.
- Stack capture for `nested_offender` shows the deepest frame as
  `_inner_compute`, not the outer coroutine.

**Failure signatures**

- No warnings appear → either the lag monitor isn't started (check
  the `Diagnostics` page; lag metrics should tick on every blocking
  call) or the warning detector is mis-configured. The terminal log
  always prints `WARNING validation.blocking: rapid_offender active …`
  banners — if those are absent the script itself isn't running.
- Warnings appear but no stack capture → `BlockingStackCaptureEngine`
  is not subscribed to the detector. Check the lifespan logs.
- A single coalesced warning group covering everything → the
  warning emitter's per-task discrimination is broken; expect the
  group key to include the offender's frame identity.

**Tunable**

```
--warmup <s>   seconds of clean asyncio activity before offenders start
               (default 3.0 — lets the lag baseline settle)
```

---

## 2. `gather_dependency_runtime.py`

**Validates**

- `GatherInstrumentationEngine` events (`asyncio.gather.{created,
  child.attached, wait.started, child.completed, completed,
  cancelled, failed}`).
- Task lineage / parent-child linkage (depth, root id,
  `ancestor_chain`).
- Cascading cancellation propagation through gather hierarchies.

**Run**

```bash
asyncviz run validation/gather_dependency_runtime.py
# or: python validation/run_validation.py gather
```

**What you should see**

| Page | Expected | Why |
|---|---|---|
| **Dependencies** | Tree-shaped layouts: one parent → many children for wide fanouts; root → branches → leaves for nested cycles. Cascading-cancel iterations show entire sub-trees flipping to `cancelled` simultaneously. | The lineage tracker projects the gather hierarchy. |
| **Timeline** | Many short-lived tasks (`leaf-*`, `branch-*`) with staggered finish times. | Leaves use random sleep durations. |
| **Tasks** | A rapidly-churning task list — most rows live <1 second. The lineage column shows parents/depth. | Every gather iteration spawns + reaps many tasks. |

**Success criteria**

- At least one "wide-fanout" cycle visible on the Dependencies page
  showing a single parent with >= `--fanout-width` (default 12)
  children, all in the same gather group.
- "Nested-tree" cycles render at depth 2 (root → branch → leaf).
- After a "cascading-cancel" iteration: every task spawned by that
  cycle reaches `cancelled` state and lineage rows reflect the
  cancellation origin.

**Failure signatures**

- Dependency view stays empty → either the gather patcher isn't
  enabled, or the events are firing but not landing in the linage
  projection. Check `Diagnostics → runtime events` for
  `asyncio.gather.*` counts.
- Cancellation iterations show only the root cancelled, not the
  children → gather child cancellation isn't being patched.

**Tunable**

```
--fanout-width <n>   children per wide-fanout cycle      (default 12)
--tree-branches <n>  branches in the nested tree         (default 3)
--tree-leaves <n>    leaves per branch in nested tree    (default 4)
--cancel-every <s>   seconds between cascading-cancel demos (0=disable)
```

---

## 3. `queue_stress_runtime.py`

**Validates**

- `QueueInstrumentationEngine` raw events (`asyncio.queue.{created,
  put, get, full_wait, empty_wait, task_done, cancelled}`).
- `QueueMetricsEngine` aggregated events (`asyncio.queue.{metrics.
  updated, pressure.changed, contention.detected, saturation.
  detected}`).
- Per-queue depth / pressure projections.

**Run**

```bash
asyncviz run validation/queue_stress_runtime.py
# or: python validation/run_validation.py queue
```

**What you should see**

5 named queues with deliberately different profiles:

| Queue | Behavior | What it triggers |
|---|---|---|
| `oscillating` | maxsize=8, 2P/2C, slow consumer | Sustained empty↔full cycling — useful for the occupancy gauge. |
| `saturating` | maxsize=4, 3P/1C, bursts of 12 | Producers stall on `put()` → `full_wait` events + `saturation.detected`. |
| `starving` | maxsize=16, 1P/4C, slow producer | Consumers `wait_for(get())` → `empty_wait` events + starvation. |
| `contended` | maxsize=6, 2P/3C, slow consumer | Producer/consumer mix triggers `contention.detected`. |
| `bursty` | maxsize=10, 1P/2C, bursts of 20 | Spikes on the metrics histogram. |

**Success criteria**

- Queues page lists all 5 queues with live depth gauges.
- During a saturating burst, you can see the queue depth pin to its
  maxsize and producers visibly stall (their tasks enter WAITING
  state in the Tasks page).
- A `saturation.detected` event fires (visible in the Diagnostics
  page's recent runtime events ring) at least once per minute.
- The `starving` queue's consumers show non-zero `empty_wait`
  occurrences.

**Failure signatures**

- Only some queues appear → the queue instrumentation engine isn't
  tracking the unnamed `asyncio.Queue` instances. Each profile uses
  a different queue object; expect all 5 to be discoverable.
- All queues stay near zero depth → producers aren't being patched.
  Verify by running `python validation/queue_stress_runtime.py` with
  `--log-level DEBUG` and checking the per-queue depth logs every 3s.

---

## 4. `executor_runtime.py`

**Validates**

- `ExecutorInstrumentationEngine` events for `loop.run_in_executor`
  (work.submitted, started, completed, failed, cancelled) against
  both `ThreadPoolExecutor` and `ProcessPoolExecutor`.
- `ExecutorMetricsEngine` aggregated events
  (`metrics.updated, saturation.changed, contention.detected,
  latency.spike.detected`).
- Cross-cutting "task spent time in an executor call" attribution.

**Run**

```bash
asyncviz run validation/executor_runtime.py
# or: python validation/run_validation.py executor

# In restricted environments where ProcessPoolExecutor can't fork:
asyncviz run validation/executor_runtime.py -- --disable-process-pool
```

**What you should see**

| Page | Expected |
|---|---|
| **Executors** | A thread pool labeled `asyncviz-validation*` with 4 workers, plus a process pool with 2 workers. Live worker-utilization gauges. The saturator cycle visibly pins thread-pool utilization at 100% during heavy CPU rounds. |
| **Diagnostics** | `saturation.changed` events landing in the recent runtime events ring at the cycle boundaries. |
| **Tasks** | Tasks `thread-baseline`, `thread-io-burst`, `thread-saturator`, `process-pool`, `mixed-scheduling` running for the duration. |

**Success criteria**

- Both thread + process pools show up as distinct executor entries
  (different `executor_kind` metadata).
- During a `thread-saturator` cycle (every ~2s) the thread pool
  saturation gauge crosses its threshold.
- `mixed-scheduling` task has a non-zero "time spent in executor"
  attribution.

**Failure signatures**

- Only the thread pool appears → process pool is failing silently
  (often the case under macOS spawn restrictions). The runtime log
  prints a warning when this happens; re-run with
  `--disable-process-pool` to confirm.
- No saturation events → the metrics engine threshold may be set
  high; check the threshold-policy config.

**Tunable**

```
--thread-workers <n>    pool size for the ThreadPoolExecutor  (default 4)
--process-workers <n>   pool size for the ProcessPoolExecutor (default 2)
--disable-process-pool  skip the process pool entirely
```

---

## 5. `semaphore_runtime.py`

**Validates**

- `SemaphoreInstrumentationEngine` events (`asyncio.semaphore.{
  created, acquire.started, acquired, released, contention.detected,
  wait.cancelled}`).
- Wait-time / hold-time projections.
- Cancellation of waiters mid-acquire.

**Run**

```bash
asyncviz run validation/semaphore_runtime.py
# or: python validation/run_validation.py semaphore
```

**What you should see**

4 named semaphores with distinct behaviors:

| Semaphore | Value | Workers | Visible effect |
|---|---|---|---|
| `contended_sem` | 2 | 12 racers | Heavy `contention.detected` rate; wait-time tail. |
| `starvation_sem` | 1 | 1 holder + 8 short-hold | Extreme wait-time outliers — holder pins permit for 3s while waiters queue. |
| `fairness_sem` | 4 | 20 churners | High acquire/release throughput; SHOULD NOT trip contention detector. |
| `cancel_sem` | 1 | demo task | Periodic burst of 4 cancelled waiters → `wait.cancelled` events. |

**Success criteria**

- Semaphores page lists all 4 instances with live permit/wait gauges.
- During a starvation cycle (every ~3s), the wait-time gauge for
  `starvation_sem` spikes to ~3000 ms.
- `fairness_sem` shows high holds/sec but zero contention events —
  validates that the detector isn't trigger-happy on light churn.
- `cancellation-demo` cycles emit `wait.cancelled` events visible in
  the Diagnostics page.

---

## 6. `mega_runtime.py`

**Validates**

Cross-cutting integration. Every subsystem above active at once, at
reduced intensity so a developer laptop can run it for several
minutes without thermal-throttling.

**Run**

```bash
asyncviz run validation/mega_runtime.py -- --duration 180
# or: python validation/run_validation.py mega -- --duration 240
```

Recommended duration **120–300 s**. Shorter runs don't give the
warning-recovery / saturation-backoff lifecycle states time to
appear.

**What you should see**

Every dashboard panel populated simultaneously:

- Queues — at least one queue oscillating, one bursting.
- Semaphores — a small permit pool under sustained contention.
- Dependencies — periodic gather trees + cascading cancels.
- Executors — thread-pool baseline + bursts.
- Warnings — one critical group from the blocking offender plus
  occasional warning-tier groups from burst-blocking.
- Tasks — 25-40 concurrent tasks at steady state, plus transient
  gather children.
- Timeline — continuous activity interleaved with freeze bars.
- Diagnostics — `runtimeEventsByCategory` shows non-zero counts for
  `asyncio.queue`, `asyncio.task`, `asyncio.gather`,
  `asyncio.semaphore`, `asyncio.executor`, and `asyncio.loop`.

**Success criteria**

- After ~30 seconds, every navigation entry on the dashboard
  (Overview, Timeline, Metrics, Warnings, Queues, Semaphores,
  Dependencies, Executors, Diagnostics) shows live data.
- Closing the page + reopening (after the shell remounts) auto-
  reconnects and re-hydrates — the connection badge transitions
  Disconnected → Hydrating → Connecting → Live within ~2 s.

**Failure signatures**

- Any one panel stays empty while others fill → that subsystem's
  bridge isn't wired. Cross-check by running the focused runtime
  for that subsystem on its own.

**Tunable**

```
--disable-blocking   run without the blocking offenders (no warnings)
```

---

## Validation strategy

Recommended order when validating a clean checkout:

1. **`blocking_runtime.py`** — establishes that the warning pipeline
   works end-to-end. Warnings are the most user-visible signal that
   instrumentation is reaching the UI.
2. **`queue_stress_runtime.py`** — validates that aggregated
   metrics events (the `metrics_delta` channel) reach the store
   correctly, since queue metrics are the most frequent producer
   of those.
3. **`gather_dependency_runtime.py`** — validates lineage tracking,
   which depends on the asyncio patcher's parent attribution being
   correct.
4. **`semaphore_runtime.py`** — sanity-check the wait/hold attribution
   on the second-most-common contention primitive.
5. **`executor_runtime.py`** — validates the cross-cutting
   "executor-time attribution" feature, which sits across the
   asyncio + executor patchers.
6. **`mega_runtime.py`** — final smoke. Should be a non-event if
   1–5 all passed.

Each focused runtime takes ~90 seconds; the mega run takes ~180 s.
Full pass < 15 minutes.

### Instrumentation coverage matrix

| Subsystem | Backend module | Validated by |
|---|---|---|
| `asyncio.task.*` | `asyncviz/instrumentation/asyncio` | every runtime (task lifecycle is always observed) |
| `asyncio.queue.*` | `asyncviz/instrumentation/queue` | `queue_stress`, `mega` |
| `asyncio.queue.metrics.*` / `pressure.*` / `contention.*` / `saturation.*` | `asyncviz/instrumentation/queue/metrics.py` | `queue_stress`, `mega` |
| `asyncio.gather.*` | `asyncviz/instrumentation/gather` | `gather_dependency`, `mega` |
| `asyncio.semaphore.*` | `asyncviz/instrumentation/semaphore` | `semaphore`, `mega` |
| `asyncio.executor.*` | `asyncviz/instrumentation/executor` | `executor`, `mega` |
| `asyncio.executor.metrics.*` | `asyncviz/instrumentation/executor/metrics.py` | `executor`, `mega` |
| `asyncio.loop.blocked` | `asyncviz/runtime/monitoring/event_loop` | `blocking`, `mega` |
| Blocking stack capture | `asyncviz/runtime/monitoring/blocking/stack_capture` | `blocking` (especially the nested offender) |
| Warning group lifecycle | `asyncviz/runtime/warnings/blocking` | `blocking`, `mega` |
| Metrics aggregator deltas | `asyncviz/runtime/metrics` | every runtime (folds into `metrics_delta`) |
| Timeline segment engine | `asyncviz/runtime/timeline` | every runtime (folds into `timeline_delta`) |

### Inspecting logs

Every runtime prints structured logs to stderr in the format:

```
2026-05-26 19:14:41,780 INFO validation.<subsystem>: <message>
```

Filter for one subsystem:

```bash
asyncviz run validation/mega_runtime.py 2>&1 | grep validation.mega
```

The terminal log is the canonical "what did the workload think it
did" record; the dashboard is the canonical "what did the
instrumentation observe" record. If those disagree, the bug is
inside the instrumentation pipeline (not the workload).
