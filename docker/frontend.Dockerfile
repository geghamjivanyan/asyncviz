# syntax=docker/dockerfile:1.7
# Multi-stage AsyncViz frontend image.
#   - deps    : install node_modules with full layer caching on package.json
#   - dev     : Vite dev server, expects bind-mounted source + named-volume node_modules
#   - builder : runs the production build (tsc -b && vite build)
#   - runtime : nginx serving the compiled SPA with /api + /ws reverse-proxy

ARG NODE_VERSION=20

# ──────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; \
    else npm install --no-audit --no-fund; fi

# ──────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
RUN chown -R node:node /app
ENV CHOKIDAR_USEPOLLING=true \
    WATCHPACK_POLLING=true \
    HOST=0.0.0.0
USER node
EXPOSE 5173
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:5173/ || exit 1
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# ──────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
RUN npm run build

# ──────────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime
COPY docker/frontend.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
