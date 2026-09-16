# Lume

Lume is a web-first, API-first personal finance platform for understanding daily
spending and staying within a monthly budget. It combines a fast phone-friendly
transaction flow with accounts, categories, recurring expectations, focused
reports, and a restrained dashboard.

The repository is public portfolio work, but the application handles real private
financial data. Ownership checks, opaque revocable sessions, CSRF protection,
fixed-point money, explicit migrations, encrypted backups, and private monitoring
are part of the core design.

## Stack

- FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, MariaDB 11.4 LTS, Python 3.14
- React 19, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod
- Tailwind CSS 4 with project-owned accessible components
- Nginx gateway, Docker Compose, Prometheus metrics, pytest, Ruff, mypy, Vitest

## Current v1 capabilities

- closed-registration authentication for browser cookies and future mobile bearer sessions;
- accounts including simple credit-card liabilities;
- income, expenses, transfers, voiding, and retry-safe creation;
- user-owned categories and overall/category monthly budgets;
- recurring income/expense expectations with explicit record or skip actions;
- dashboard totals, category ranking, six-month trend, and largest expenses;
- CSV transaction export protected against spreadsheet formula injection;
- responsive public site and installable online-only PWA shell;
- structured logs, request IDs, private metrics, readiness, and login throttling.

## Local development

Requirements are Docker with Compose v2, Node 24 for host-side frontend commands,
and GNU Make. Copy the development environment template, start the stack, then
create the first user:

```bash
cp .env.example .env
make dev
make dev-admin EMAIL=owner@example.com NAME='Lume Owner'
```

The password prompt does not place the password in shell history. Open
`http://127.0.0.1:15173`; the API is also available at
`http://127.0.0.1:18100/api/v1/docs`. Development state belongs to `lume-dev` and
is separate from both tests and production.

Common checks:

```bash
make test
make lint
make typecheck
make build
make compose-validate
make api-contract
```

The disposable test project uses a MariaDB tmpfs. Tests never use the development
or production database.

## Architecture

Lume is a modular monolith. The React client consumes the same versioned REST API
intended for a future native client. Production uses three long-running containers:
the Nginx gateway, FastAPI API, and dedicated MariaDB database. Only the gateway
joins the VPS `web-proxy` network; the API joins the private application networks
and the existing private monitoring network.

Read [Architecture](docs/ARCHITECTURE.md), [Deployment](docs/DEPLOYMENT.md), and
[Backup and restore](docs/BACKUP_RESTORE.md) for operational detail. The original
[implementation plan](docs/IMPLEMENTATION_PLAN.md) records the scope and decisions
that guided v1.

## API contract

The OpenAPI document is committed at [docs/openapi.json](docs/openapi.json), and
the frontend types are generated from it. Run `make api-contract` after changing an
API schema and commit both outputs. Interactive documentation lives at
`/api/v1/docs`.

## Production status

Production images and Compose configuration are implemented, but this repository
does not alter the shared edge, TLS certificate, monitoring configuration, or live
services by itself. Public launch requires the separately reviewed steps in the
deployment runbook.

## License

No license has been selected yet. All rights are reserved until one is added.
