SHELL := /bin/bash
VENV_BIN := .venv/bin

.PHONY: help \
        install install-backend install-frontend \
        dev backend frontend \
        lint lint-backend lint-frontend \
        format format-backend format-frontend \
        test test-backend \
        typecheck typecheck-frontend \
        build build-frontend embed-frontend clean-frontend verify-frontend \
        package package-smoke package-wheel package-sdist \
        package-verify package-clean release-check \
        ci ci-backend ci-frontend \
        clean doctor check-ports kill-stale \
        docker-build docker-up docker-down docker-logs docker-reset docker-exec

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "AsyncViz make targets:\n\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ── install ────────────────────────────────────────────────────────────────
install: install-backend install-frontend ## Install backend + frontend deps

install-backend: ## Create .venv and install asyncviz[dev]
	@scripts/backend/install.sh

install-frontend: ## Install frontend deps via npm
	@scripts/frontend/install.sh

# ── dev ────────────────────────────────────────────────────────────────────
dev: ## Run backend + frontend together
	@scripts/dev/start-all.sh

backend: ## Run only the backend dev server
	@scripts/dev/start-backend.sh

frontend: ## Run only the frontend dev server
	@scripts/dev/start-frontend.sh

# ── lint / format ──────────────────────────────────────────────────────────
lint: lint-backend lint-frontend ## Lint backend + frontend

lint-backend: ## Ruff check + format check
	@scripts/backend/lint.sh

lint-frontend: ## ESLint + Prettier check
	@scripts/frontend/lint.sh

format: format-backend format-frontend ## Format backend + frontend

format-backend: ## Ruff format + --fix
	@scripts/backend/format.sh

format-frontend: ## Prettier write + ESLint --fix
	@scripts/frontend/format.sh

# ── test / typecheck / build ───────────────────────────────────────────────
test: test-backend ## Run all tests

test-backend: ## Pytest with coverage
	@scripts/backend/test.sh --cov

typecheck: typecheck-frontend ## Type-check the codebase

typecheck-frontend: ## TypeScript strict check
	@scripts/frontend/typecheck.sh

build: build-frontend ## Build production artifacts

build-frontend: ## Vite production build (writes to frontend/dist)
	@scripts/frontend/build.sh

embed-frontend: ## Build the frontend and copy it into asyncviz/dashboard/static
	@scripts/frontend/build-prod.sh

clean-frontend: ## Remove the embedded frontend bundle
	@scripts/frontend/clean-static.sh

verify-frontend: ## Sanity-check the embedded frontend bundle
	@scripts/frontend/verify-static.sh

package: ## Build wheel + sdist with the embedded frontend (canonical entry point)
	@$(VENV_BIN)/python scripts/packaging/package_frontend.py

package-wheel: ## Build only a wheel artifact
	@$(VENV_BIN)/python scripts/packaging/package_frontend.py --wheel-only

package-sdist: ## Build only an sdist artifact
	@$(VENV_BIN)/python scripts/packaging/package_frontend.py --sdist-only

package-verify: ## Validate artifacts in dist/ (asset presence, schema, integrity)
	@$(VENV_BIN)/python scripts/packaging/verify_package.py

package-clean: ## Remove every packaging artifact (dist/, build/, embed)
	@$(VENV_BIN)/python scripts/packaging/clean_build.py

release-check: ## Run the canonical pre-release gate (version + bundle + artifacts)
	@$(VENV_BIN)/python scripts/packaging/release_checks.py

package-smoke: ## Build a wheel, install it in a fresh venv, and verify the UI loads
	@scripts/ci/package-smoke.sh

# ── ci ─────────────────────────────────────────────────────────────────────
ci: ## Run the full local CI matrix
	@scripts/ci/all.sh

ci-backend: ## Run only the backend CI pipeline
	@scripts/ci/backend.sh

ci-frontend: ## Run only the frontend CI pipeline
	@scripts/ci/frontend.sh

# ── utils ──────────────────────────────────────────────────────────────────
clean: ## Remove caches and build artifacts
	@scripts/utils/clean.sh

doctor: ## Check local environment health
	@scripts/utils/doctor.sh

check-ports: ## Show whether AsyncViz dev ports are free
	@scripts/utils/check-ports.sh

kill-stale: ## List stale AsyncViz/Vite processes (use FORCE=1 to terminate)
	@if [ "$(FORCE)" = "1" ]; then scripts/utils/kill-stale.sh --force; else scripts/utils/kill-stale.sh; fi

# ── docker ─────────────────────────────────────────────────────────────────
docker-build: ## Build all containers
	@scripts/docker/build.sh

docker-up: ## Start the stack (detached)
	@scripts/docker/up.sh

docker-down: ## Stop the stack (keeps named volumes)
	@scripts/docker/down.sh

docker-logs: ## Tail container logs (pass SERVICE=name to scope)
	@scripts/docker/logs.sh $(SERVICE)

docker-reset: ## Stop the stack and remove its volumes
	@scripts/docker/reset.sh

docker-exec: ## Open a shell in a running service (SERVICE=backend|frontend)
	@scripts/docker/exec.sh $(SERVICE)
