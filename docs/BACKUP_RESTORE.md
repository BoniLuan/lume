# Backup and restore

CSV export is for user portability. It is not a database backup.

## Encrypted backup

Install `age` on the operator host and configure the public recipient file described
in [Deployment](DEPLOYMENT.md). Then run:

```bash
make backup
```

The script executes `mariadb-dump --single-transaction` inside the matching
MariaDB container, includes routines/triggers/events, compresses the stream, and
encrypts it before writing to `/home/luan/backups/lume`. It emits a SHA-256 sidecar
and never passes a database password on the host command line.

Copy encrypted artifacts and checksums off the VPS. Initial retention is 14 daily
and 8 weekly backups once scheduling is enabled. The target RPO is 24 hours and RTO
is two hours. Scheduling and the off-host destination remain operator decisions.

## Restore verification

Keep the matching private age identity outside the repository and run:

```bash
make restore-verify FILE=/home/luan/backups/lume/lume-YYYYMMDDTHHMMSSZ.sql.gz.age
```

The drill verifies the checksum when present, creates uniquely named private Docker
network/volume/container resources, restores into a fresh MariaDB 11.4 instance,
starts the candidate API image, requires migration-aware readiness, prints table row
estimates, and removes only drill-owned resources on exit.

Set `LUME_API_IMAGE` to the exact candidate release and
`LUME_AGE_IDENTITY_FILE` to the private key path when their defaults do not apply.
Inspect representative account balances, budgets, recurrence, and ownership after
the automated readiness check for release-critical restores.

Never test restoration against `lume_mariadb_data`, and never decrypt a production
backup into the repository or a shared temporary directory.
