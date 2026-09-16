SHELL := /bin/sh

DEV_COMPOSE := docker compose -p lume-dev -f compose.dev.yaml
TEST_COMPOSE := docker compose -p lume-test -f compose.test.yaml
PROD_COMPOSE := docker compose -p lume -f compose.prod.yaml

.PHONY: help monitoring-prepare dev dev-down dev-status dev-logs dev-admin migrate migration test test-backend test-frontend lint lint-backend lint-frontend typecheck typecheck-backend typecheck-frontend build build-frontend format-check compose-validate prod-validate prod-build prod-migrate prod-up admin-create backup restore-verify api-contract

help:
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

monitoring-prepare: ## Merge Lume into the active shared Prometheus configuration
	python3 scripts/prepare-monitoring.py /home/luan/projects/relay/.local/prometheus.integrated.yml .local/prometheus.integrated.yml

dev: ## Start the isolated development database, API, and web client
	$(DEV_COMPOSE) up -d --build db
	$(DEV_COMPOSE) --profile tools run --rm migrate
	$(DEV_COMPOSE) up -d --build api web

dev-down: ## Stop development services while retaining development data
	$(DEV_COMPOSE) down

dev-status: ## Show development service status
	$(DEV_COMPOSE) ps

dev-logs: ## Follow development application logs
	$(DEV_COMPOSE) logs -f api web db

dev-admin: ## Interactively create a development user; usage: make dev-admin EMAIL=... NAME='...'
	@test -n "$(EMAIL)" || (echo "EMAIL is required" >&2; exit 2)
	@test -n "$(NAME)" || (echo "NAME is required" >&2; exit 2)
	$(DEV_COMPOSE) run --rm api lume-admin create-user --email "$(EMAIL)" --display-name "$(NAME)"

migrate: ## Apply migrations to the development database explicitly
	$(DEV_COMPOSE) --profile tools run --rm migrate

migration: ## Create a migration; usage: make migration NAME=description
	@test -n "$(NAME)" || (echo "NAME is required" >&2; exit 2)
	$(DEV_COMPOSE) --profile tools run --rm migrate alembic revision --autogenerate -m "$(NAME)"

test: test-backend test-frontend ## Run backend and frontend tests

test-backend: ## Run backend tests against the disposable test stack
	$(TEST_COMPOSE) up --build --abort-on-container-exit --exit-code-from tests tests
	$(TEST_COMPOSE) down --volumes --remove-orphans

test-frontend: ## Run frontend unit tests
	cd frontend && npm test

lint: lint-backend lint-frontend ## Run all lint checks

lint-backend: ## Run backend lint checks in an isolated container
	docker build --target development -t lume-api-check:local backend
	docker run --rm --network none lume-api-check:local ruff check --no-cache .

lint-frontend: ## Run frontend lint checks
	cd frontend && npm run lint

format-check: ## Check backend formatting without changing files
	docker build --target development -t lume-api-check:local backend
	docker run --rm --network none lume-api-check:local ruff format --check --no-cache .

typecheck: typecheck-backend typecheck-frontend ## Run all static type checking

typecheck-backend: ## Run backend static type checking
	docker build --target development -t lume-api-check:local backend
	docker run --rm --network none --tmpfs /tmp:rw,mode=1777 lume-api-check:local mypy --cache-dir=/tmp/mypy-cache src tests

typecheck-frontend: ## Run frontend static type checking
	cd frontend && npm run typecheck

build: build-frontend ## Build production artifacts

build-frontend: ## Build the production web client
	cd frontend && npm run build

api-contract: ## Regenerate OpenAPI and TypeScript API types
	docker build --target development -t lume-api-check:local backend
	docker run --rm --network none -e LUME_DATABASE_PASSWORD=openapi-only lume-api-check:local python -c 'import json; from lume.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))' > docs/openapi.json
	cd frontend && npm run generate:api

compose-validate: ## Validate development and test Compose files
	$(DEV_COMPOSE) config --quiet
	$(TEST_COMPOSE) config --quiet

prod-validate: ## Validate resolved production Compose configuration
	$(PROD_COMPOSE) config --quiet

prod-build: ## Build local production API and gateway images
	$(PROD_COMPOSE) build api gateway

prod-migrate: ## Explicitly apply production migrations
	$(PROD_COMPOSE) --profile tools run --rm migrate

prod-up: ## Reconcile the Lume production services after migration
	$(PROD_COMPOSE) up -d --no-build db api gateway

admin-create: ## Interactively create a user; usage: make admin-create EMAIL=... NAME='...'
	@test -n "$(EMAIL)" || (echo "EMAIL is required" >&2; exit 2)
	@test -n "$(NAME)" || (echo "NAME is required" >&2; exit 2)
	$(PROD_COMPOSE) --profile tools run --rm admin create-user --email "$(EMAIL)" --display-name "$(NAME)"

backup: ## Create an encrypted production database backup
	./scripts/backup.sh

restore-verify: ## Restore an encrypted backup in isolation; usage: make restore-verify FILE=...
	@test -n "$(FILE)" || (echo "FILE is required" >&2; exit 2)
	./scripts/restore-verify.sh "$(FILE)"
