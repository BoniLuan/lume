SHELL := /bin/sh

DEV_COMPOSE := docker compose -p lume-dev -f compose.dev.yaml
TEST_COMPOSE := docker compose -p lume-test -f compose.test.yaml

.PHONY: help dev dev-down dev-status dev-logs migrate migration test test-backend lint typecheck format-check compose-validate

help:
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dev: ## Start the isolated development database and API
	$(DEV_COMPOSE) up -d --build db api

dev-down: ## Stop development services while retaining development data
	$(DEV_COMPOSE) down

dev-status: ## Show development service status
	$(DEV_COMPOSE) ps

dev-logs: ## Follow development API and database logs
	$(DEV_COMPOSE) logs -f api db

migrate: ## Apply migrations to the development database explicitly
	$(DEV_COMPOSE) --profile tools run --rm migrate

migration: ## Create a migration; usage: make migration NAME=description
	@test -n "$(NAME)" || (echo "NAME is required" >&2; exit 2)
	$(DEV_COMPOSE) --profile tools run --rm migrate alembic revision --autogenerate -m "$(NAME)"

test: test-backend ## Run the complete test suite currently available

test-backend: ## Run backend tests against the disposable test stack
	$(TEST_COMPOSE) up --build --abort-on-container-exit --exit-code-from tests tests
	$(TEST_COMPOSE) down --volumes --remove-orphans

lint: ## Run backend lint checks in an isolated container
	docker build --target development -t lume-api-check:local backend
	docker run --rm --network none lume-api-check:local ruff check --no-cache .

format-check: ## Check backend formatting without changing files
	docker build --target development -t lume-api-check:local backend
	docker run --rm --network none lume-api-check:local ruff format --check --no-cache .

typecheck: ## Run backend static type checking
	docker build --target development -t lume-api-check:local backend
	docker run --rm --network none --tmpfs /tmp:rw,mode=1777 lume-api-check:local mypy --cache-dir=/tmp/mypy-cache src tests

compose-validate: ## Validate development and test Compose files
	$(DEV_COMPOSE) config --quiet
	$(TEST_COMPOSE) config --quiet
