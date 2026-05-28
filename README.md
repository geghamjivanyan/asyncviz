# AsyncViz

Real-time runtime visualization and debugging platform for Python `asyncio` applications.

AsyncViz instruments a running Python program, streams runtime events from the event loop,
and renders an interactive view of tasks, coroutines, and scheduling activity in the browser.

> Status: early scaffolding. Public API and behavior are not yet stable.

## Repository Layout

```
asyncviz/
├── asyncviz/             # Python package (instrumentation, runtime, collector, ws, dashboard, …)
├── frontend/             # React + TypeScript + Vite dashboard
├── examples/             # Sample asyncio applications
├── tests/                # Pytest suite (unit/ + integration/)
├── scripts/              # Shared dev/CI scripts (see below)
├── docker/               # Backend & frontend Dockerfiles
├── .github/workflows/    # CI pipelines (delegate to scripts/ci/)
├── pyproject.toml
├── Makefile              # Thin command surface that delegates to scripts/
├── .pre-commit-config.yaml
├── .editorconfig
├── .env.example          # Backend env vars (ASYNCVIZ_*)
└── docker-compose.yml
```

## Requirements

- Python 3.12+
- Node.js 20+
- bash 3.2+ (default on macOS) — scripts are POSIX-friendly

## Local Development

```bash
make install     # create .venv, install backend + frontend deps
make doctor      # sanity-check the local environment
make dev         # run backend + frontend together with prefixed output
```

`make dev` spawns each side in its own process group and shuts both down on
Ctrl+C. Output is prefixed `[backend]` / `[frontend]` and color-coded when
attached to a TTY.

Need just one side?

```bash
make backend     # python -m asyncviz on http://127.0.0.1:8877
make frontend    # Vite dev server on http://127.0.0.1:5173
```

The Vite dev server proxies `/api` and `/ws` to the backend so the frontend
talks to AsyncViz without CORS issues.

## Environment

Copy the example and customize for local development:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Backend variables (loaded automatically by `python -m asyncviz`):

| Variable                 | Default       | Purpose                                  |
| ------------------------ | ------------- | ---------------------------------------- |
| `ASYNCVIZ_HOST`          | `127.0.0.1`   | Bind address for the dashboard server    |
| `ASYNCVIZ_PORT`          | `8877`        | Dashboard server port                    |
| `ASYNCVIZ_OPEN_BROWSER`  | `true`        | Open the dashboard in your browser       |
| `ASYNCVIZ_DEBUG`         | `false`       | Verbose logging + FastAPI debug          |

Frontend variables are loaded by Vite from `frontend/.env*`. They must be
prefixed `VITE_`:

| Variable               | Default                       | Purpose                          |
| ---------------------- | ----------------------------- | -------------------------------- |
| `VITE_RUNTIME_WS_URL`  | `ws://127.0.0.1:8877/ws`      | Backend WebSocket endpoint       |

## Make Targets

```
make help
```

| Target            | What it runs                                         |
| ----------------- | ---------------------------------------------------- |
| `install`         | Backend (`.venv` + deps) and frontend deps           |
| `dev`             | Backend + frontend together (Python orchestrator)    |
| `backend`         | Only the backend                                     |
| `frontend`        | Only the Vite dev server                             |
| `lint`            | Ruff + ESLint + Prettier check                       |
| `format`          | Ruff format + Prettier write + ESLint --fix          |
| `test`            | `pytest --cov`                                       |
| `typecheck`       | TypeScript strict check                              |
| `build`           | Vite production build                                |
| `embed-frontend`  | Build + embed the SPA into `asyncviz/dashboard/static/` |
| `clean-frontend`  | Remove the embedded SPA bundle                        |
| `package`         | Build a wheel with the embedded frontend baked in    |
| `package-smoke`   | Build + install wheel in a fresh venv + verify UI    |
| `ci`              | Full local CI matrix (`scripts/ci/all.sh`)           |
| `clean`           | Remove caches and build outputs                      |
| `doctor`          | Validate Python/Node versions + ports                |
| `check-ports`     | Show whether AsyncViz dev ports are free             |
| `kill-stale`      | List stale processes (`FORCE=1` to terminate)        |

## Scripts

The Makefile is a thin command surface — actual logic lives under
`scripts/` and is the **single source of truth** shared by Make, pre-commit
hooks, and GitHub Actions.

```
scripts/
├── backend/    install, run, lint, format, test
├── frontend/   install, run, lint, format, typecheck, build,
│               build-prod, sync-static, clean-static, verify-static
├── dev/        start.py (orchestrator) + start-{all,backend,frontend}.sh
├── ci/         backend.sh, frontend.sh, all.sh, package-smoke.sh
├── docker/     build, up, down, logs, reset, exec
└── utils/      lib.sh, clean.sh, doctor.sh, check-ports.sh, kill-stale.sh
```

## Embedded distribution

AsyncViz ships the compiled React SPA inside its Python package, so a
plain `pip install` is enough to get the full dashboard — no separate
frontend process, no Node runtime required in production.

```bash
make embed-frontend        # npm run build → asyncviz/dashboard/static/
make package               # build a wheel with the SPA included
make package-smoke         # wheel build + install in fresh venv + UI smoke
```

The build/embed flow:

```
frontend/src/  ──► npm run build  ──► frontend/dist/
                                          │
                                          ▼ scripts/frontend/sync-static.sh
                              asyncviz/dashboard/static/
                                          │
                                          ▼ hatch builds wheel
                                   asyncviz-0.1.0-*.whl
                                          │
                                          ▼ pip install
              site-packages/asyncviz/dashboard/static/{index.html,assets/*}
                                          │
                                          ▼ FastAPI serves it
                          http://localhost:8877  (embedded UI)
```

### Dev vs. production behavior

The backend automatically picks the right mode based on whether
`asyncviz/dashboard/static/index.html` exists:

| Mode        | Trigger                                      | Behavior                                                  |
| ----------- | -------------------------------------------- | --------------------------------------------------------- |
| Embedded    | `index.html` present in the package's static dir | FastAPI serves `/` (SPA), `/assets/*` (immutable cache), `/api/*`, `/ws` |
| API-only    | static dir empty (typical for dev checkouts) | FastAPI serves `/api/*` and `/ws` only — frontend runs separately via `make frontend` |

Caching policy:

- `/assets/*` (Vite-hashed) → `Cache-Control: public, max-age=31536000, immutable`
- Loose files (`favicon.ico`, `robots.txt`, …) → `Cache-Control: public, max-age=3600`
- `index.html` / SPA fallback → `Cache-Control: no-cache` (so updates roll out)

Every shell script sources `scripts/utils/lib.sh` for repo-root resolution
and colorized logging. The dev orchestrator (`scripts/dev/start.py`) handles
multi-process supervision: it spawns each side in its own process group,
prefixes stdout/stderr, and propagates SIGINT / SIGTERM cleanly to both
children. Pass `NO_COLOR=1` to disable ANSI color output.

## Validation

Run the same checks CI runs, locally:

```bash
make ci          # full repository validation
make ci-backend  # only backend
make ci-frontend # only frontend
```

Or invoke pieces directly:

```bash
scripts/backend/lint.sh
scripts/backend/test.sh --cov
scripts/frontend/lint.sh
scripts/frontend/typecheck.sh
scripts/frontend/build.sh
```

## Pre-commit

```bash
.venv/bin/pre-commit install
```

The hooks (Ruff format + check, frontend ESLint, Prettier, tsc) match the CI
pipeline exactly.

## Docker

A complete dev stack — backend (`uvicorn --reload`) plus frontend (Vite HMR) —
runs in containers with a single command:

```bash
make docker-up          # builds on first run, starts in detached mode
make docker-logs        # tail logs from both services
make docker-down        # stop containers (keeps the node_modules volume)
make docker-reset       # nuke containers + volumes for a fresh start
```

Exposed ports match the host workflow: backend on **:8877**, frontend on
**:5173**. Both services live on the internal `asyncviz` bridge network, and
the frontend container reaches the backend at `http://backend:8877` via the
parameterized Vite proxy (`BACKEND_URL` env var).

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ docker-compose (network: asyncviz)                                  │
│                                                                     │
│  ┌──────────────────────────┐      ┌──────────────────────────────┐ │
│  │ backend (target: dev)    │ ───▶ │ frontend (target: dev)       │ │
│  │ python:3.12-slim         │ HC   │ node:20-alpine               │ │
│  │ uvicorn --reload         │      │ vite dev --host 0.0.0.0      │ │
│  │ bind: ./asyncviz         │      │ bind: ./frontend             │ │
│  │ user: asyncviz (1000)    │      │ user: node (1000)            │ │
│  │ port 8877                │      │ volume: frontend_node_modules│ │
│  └─────────┬────────────────┘      └────────────────┬─────────────┘ │
└────────────┼─────────────────────────────────────────┼──────────────┘
             ▼                                         ▼
    host :8877 → /api, /ws                  host :5173 → SPA + HMR
```

Each Dockerfile is multi-stage. The compose stack targets the `dev` stage;
the `runtime` stage builds a lean production image (nginx for the frontend,
`python -m asyncviz` for the backend).

### Caching

- Backend: `pyproject.toml` and `README.md` are copied **before** the source,
  so any change to source code doesn't bust the pip layer.
- Frontend: `package.json` / `package-lock.json` are copied before the
  source, and the `npm ci` layer uses BuildKit's `--mount=type=cache` for
  the npm download cache.
- Frontend `node_modules` lives in a **named volume**, so the host bind mount
  doesn't shadow what the container installed.

### Hot reload

- **Backend** — `uvicorn --reload` watches `/app/asyncviz`, which is the bind
  mount from the host. Edit a `.py` file → uvicorn reloads.
- **Frontend** — Vite HMR with polling enabled (`CHOKIDAR_USEPOLLING=true`)
  so file events propagate through Docker Desktop on macOS too.

### Production build

```bash
# Single self-contained image: Python + embedded SPA, no external nginx.
docker build -f docker/backend.Dockerfile  --target runtime -t asyncviz-backend:prod .

# Optional: split-deploy image where nginx serves the SPA + reverse-proxies the API.
docker build -f docker/frontend.Dockerfile --target runtime -t asyncviz-frontend:prod .
```

The backend runtime image now ships the compiled SPA inside the package:
a separate `frontend-builder` stage (Node 20) compiles `frontend/dist`,
which is copied into `/app/asyncviz/dashboard/static/`. The runtime image
itself contains **no Node.js** — Python + the static bundle is enough.

The frontend runtime image (nginx-based) remains as an alternative for
deployments that prefer to split the SPA into a separate container with
its own `/api` + `/ws` reverse-proxy (see `docker/frontend.nginx.conf`).

## Troubleshooting

**`Address already in use` on port 8877 or 5173**
```bash
make check-ports          # diagnose
make kill-stale FORCE=1   # terminate stragglers
```

**`python3 not found` when running `make dev`**
You probably skipped `make install`. That target creates `.venv/` which the
orchestrator prefers; without it, ensure `python3` is on `PATH`.

**Frontend hot reload not picking up the backend**
The Vite proxy targets `http://127.0.0.1:8877`. If you changed
`ASYNCVIZ_HOST`/`ASYNCVIZ_PORT`, update `frontend/vite.config.ts` to match,
or set `VITE_RUNTIME_WS_URL` in `frontend/.env.local`.

**Docker: file changes not reflected**
Hot reload uses polling inside containers (`CHOKIDAR_USEPOLLING=true`,
uvicorn's watcher on the bind mount). If polling is disabled or the bind
mount went stale, `make docker-reset && make docker-up` rebuilds cleanly.

**Docker: `node_modules` keeps re-installing**
The frontend uses a named volume for `node_modules` to avoid the host bind
mount shadowing it. `make docker-reset` drops the volume — useful after a
`package.json` change but otherwise unnecessary.

**Docker: port already allocated**
`make docker-down` then `make check-ports` to identify any non-Docker
process still bound. Override the host ports with
`ASYNCVIZ_PORT=18877 VITE_PORT=15173 make docker-up`.

**`make dev` doesn't fully exit on Ctrl+C**
The orchestrator gives each child ~6 seconds to shut down on SIGINT before
escalating to SIGTERM. If you still see stragglers, `make kill-stale FORCE=1`.

**Ruff or ESLint cache yields stale results**
```bash
make clean
```

## Architecture

> _Placeholder — to be filled in as components stabilize._

AsyncViz is composed of:

- **instrumentation** — hooks into the asyncio event loop to capture task and coroutine events.
- **runtime** — in-process supervisor that owns the AsyncViz lifecycle.
- **collector** — buffers and normalizes raw events into structured records.
- **websocket** — streams events to connected dashboard clients.
- **dashboard** — server-side glue exposing the frontend.
- **models** — shared data types.
- **cli** — command-line entry points.

The **frontend** subscribes to the websocket stream and renders the live runtime view.

## License

MIT. See `LICENSE`.
