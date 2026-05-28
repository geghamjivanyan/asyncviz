# syntax=docker/dockerfile:1.7
# Multi-stage AsyncViz backend image.
#   - base             : python:slim with a shared venv path on PATH
#   - builder          : produces /opt/venv with non-editable backend install
#   - frontend-builder : node:alpine that compiles the Vite SPA
#   - dev              : adds [dev] extras + bind-mounted source + uvicorn --reload
#   - runtime          : final lean image, non-root, backend + embedded frontend

ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=20

# ──────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PATH="/opt/venv/bin:${PATH}"

# ──────────────────────────────────────────────────────────────────────────────
FROM base AS builder

WORKDIR /build
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip
COPY pyproject.toml README.md LICENSE ./
COPY asyncviz ./asyncviz
RUN pip install .

# ──────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; \
    else npm install --no-audit --no-fund; fi
COPY frontend/ ./
RUN npm run build

# ──────────────────────────────────────────────────────────────────────────────
FROM base AS dev

ENV ASYNCVIZ_HOST=0.0.0.0 \
    ASYNCVIZ_PORT=8877 \
    ASYNCVIZ_OPEN_BROWSER=false \
    ASYNCVIZ_DEBUG=false

RUN groupadd --system --gid 1000 asyncviz \
 && useradd --system --uid 1000 --gid asyncviz --create-home --home /home/asyncviz asyncviz \
 && mkdir -p /app && chown asyncviz:asyncviz /app

WORKDIR /app
RUN python -m venv /opt/venv \
 && chown -R asyncviz:asyncviz /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip

COPY --chown=asyncviz:asyncviz pyproject.toml README.md LICENSE ./
COPY --chown=asyncviz:asyncviz asyncviz ./asyncviz

USER asyncviz
RUN pip install -e ".[dev]"

EXPOSE 8877

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8877/api/health', timeout=2).status==200 else 1)"

CMD ["uvicorn", "asyncviz.dashboard.asgi:app", \
     "--host", "0.0.0.0", "--port", "8877", \
     "--reload", "--reload-dir", "/app/asyncviz"]

# ──────────────────────────────────────────────────────────────────────────────
FROM base AS runtime

ENV ASYNCVIZ_HOST=0.0.0.0 \
    ASYNCVIZ_PORT=8877 \
    ASYNCVIZ_OPEN_BROWSER=false \
    ASYNCVIZ_DEBUG=false

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/asyncviz ./asyncviz
COPY --from=builder /build/pyproject.toml /build/README.md /build/LICENSE ./
# Bake the compiled frontend into the embedded static directory so the runtime
# image is self-contained — no Node and no separate frontend container needed.
COPY --from=frontend-builder /frontend/dist ./asyncviz/dashboard/static

RUN groupadd --system --gid 1000 asyncviz \
 && useradd --system --uid 1000 --gid asyncviz --no-create-home asyncviz \
 && chown -R asyncviz:asyncviz /app /opt/venv

USER asyncviz

EXPOSE 8877

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8877/api/health', timeout=2).status==200 else 1)"

CMD ["python", "-m", "asyncviz"]
