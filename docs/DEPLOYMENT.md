# Production deployment

This runbook prepares Lume without modifying the shared VPS edge. Public activation
is a separate reviewed operation because the current origin certificate and edge
configuration must be updated without interrupting existing applications.

## One-time preparation

The production host needs the external `web-proxy` and `vigil-monitoring` networks.
Create private secret files once:

```bash
./scripts/init-secrets.sh
```

Files live under `/home/luan/.config/lume` with directory mode `0700` and file mode
`0444`. Compose file-backed secrets are bind mounts and cannot remap ownership,
so unprivileged container users require read permission on each mounted file. The
private `0700` directory prevents other host users from traversing to them. Do not
put them in the repository. Create an `age` identity, store its private key
off-host, and put only the public recipient in `backup.age-recipient`.

Validate configuration and build candidate images:

```bash
make prod-validate
make prod-build
```

For immutable releases, set `LUME_API_IMAGE` and `LUME_GATEWAY_IMAGE` to GHCR tags
based on the reviewed Git commit instead of using the local defaults.

## Release order

1. Require a clean reviewed commit and passing CI.
2. Run `make backup` and verify the checksum plus `make restore-verify FILE=...`.
3. Pull or build immutable images.
4. Run `make prod-validate` without printing resolved secrets.
5. Start MariaDB only if this is the first release:
   `docker compose -p lume -f compose.prod.yaml up -d db`.
6. Apply schema changes explicitly with `make prod-migrate`.
7. Reconcile application containers with `make prod-up`.
8. Verify `api` readiness, gateway health, and `/api/v1/openapi.json` from within
   project networks.
9. Add the `lume-api-metrics:8000/metrics` target to the existing generated
   Prometheus configuration while preserving all Vigil and Relay jobs.
10. Prepare and validate the shared edge config in its owning repository. Expand
    certificate coverage for `lume.boniluan.com` before routing public traffic.
11. Verify all existing public applications as well as Lume.
12. Record actual running allocations in `/home/luan/projects/INFRASTRUCTURE.md`.

Migrations never run inside API startup. `/readyz` returns 503 when MariaDB is
unreachable or its Alembic revision is not the application head.

## First user

After migration, create the owner through the private tools container:

```bash
make admin-create EMAIL=owner@example.com NAME='Lume Owner'
```

For a reset, run the tools service directly. It prompts securely and revokes every
active session:

```bash
docker compose -p lume -f compose.prod.yaml --profile tools run --rm \
  admin reset-password --email owner@example.com
```

## Resource envelope

The production limits are 768 MiB/0.75 CPU for MariaDB, 384 MiB/0.75 CPU for the
API, and 128 MiB/0.25 CPU for Nginx. MariaDB begins with a 320 MiB InnoDB buffer
pool and 50 connections. Docker JSON logs rotate at 10 MiB with three files.

These are starting limits for the shared 4-CPU, 7.8-GiB VPS. Review cAdvisor and
application metrics before raising them. Do not publish host ports or add a second
Prometheus/Grafana stack.

## Rollback

Application images can roll back to the preceding immutable tags when migrations
remain backward-compatible. Database rollback is restore-based: stop writes, keep
the failed state for analysis, restore the last verified encrypted backup into a
fresh volume, and verify it before switching. Do not use `alembic downgrade` as a
substitute for a recovery plan on MariaDB DDL.
