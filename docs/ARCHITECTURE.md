# Architecture

## Runtime shape

Lume is a modular monolith with one public gateway, one API process, and one
MariaDB database.

```text
Cloudflare -> shared boniluan-home edge -> web-proxy -> lume-gateway:8080
                                                   -> React static application
                                                   -> /api/v1 -> lume-api:8000
existing Prometheus -> vigil-monitoring -> lume-api-metrics:8000/metrics
lume-api -> lume_backend -> lume-db:3306
```

`lume-gateway` is the only Lume service on `web-proxy`. MariaDB has no host port.
The gateway blocks health, readiness, metrics, and internal paths from public
routing. Production networks and DNS aliases are project-prefixed where shared.

## Backend boundaries

Each module owns its models, schemas, routes, and domain services:

- `auth` and `users`: identity, passwords, revocable sessions, CSRF, profile;
- `accounts`: asset/liability containers and reconciled balances;
- `categories`: user-owned income/expense classification;
- `transactions`: income, expense, transfers, retry safety, and voiding;
- `budgets`: monthly overall and optional category limits;
- `recurring`: templates and explicitly handled occurrences;
- `reporting`: dashboard aggregation and CSV export;
- `core`: configuration, database, money, time, migrations, and observability.

Routes validate transport concerns. Services and database invariants own financial
rules. Core financial behavior never exists only in React.

## Financial invariants

- Monetary values use `DECIMAL(19,4)`, Python `Decimal`, and JSON strings.
- Transaction amounts are positive. `kind` defines their effect.
- Income and expenses require a matching category and one account.
- Transfers require distinct source/destination accounts and no category.
- Transfers do not affect income, expense, or budget totals.
- Voided transactions remain auditable and affect no balance or aggregate.
- Every relationship is checked against the authenticated owner; composite foreign
  keys also prevent cross-owner references where practical.
- User-entered financial dates are `DATE`; timestamps are UTC. Month defaults are
  determined in `America/Sao_Paulo`.

Account balance is:

```text
opening + income - expenses - outgoing transfers + incoming transfers
```

Credit cards are liability accounts. Their stored negative balance is presented as
positive “amount owed” in the web client.

## Authentication

The browser receives an opaque, secure, HttpOnly, SameSite=Lax host cookie. Only a
SHA-256 digest of the token is stored. Unsafe cookie requests require a session-
bound CSRF token and exact allowed Origin. Native clients can request the same
opaque token as a bearer credential; bearer requests do not use CSRF.

Sessions are revocable and have idle plus absolute expiry. Argon2id hashes
passwords. Registration is closed; operators create users and reset passwords with
`lume-admin`, which also revokes sessions after a reset.

## Frontend

TanStack Query owns server state. A small context exposes only the current session,
and local state handles forms and UI. The typed fetch wrapper always sends cookie
credentials and adds CSRF only to unsafe methods. Route modules are lazy-loaded.

The PWA caches the static application shell and hashed assets. API and authentication
responses have no runtime cache rule, and the production gateway marks API replies
`no-store`. Offline writes and background sync are intentionally absent.

## Decisions deferred beyond v1

Card statement cycles, installments, bank imports, Open Finance, notifications,
goals, investments, shared households, multiple currencies, and native mobile are
outside v1. Recurring templates remain expectations; they do not silently create
financial transactions.
