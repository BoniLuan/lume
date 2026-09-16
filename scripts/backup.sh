#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="${LUME_BACKUP_DIR:-/home/luan/backups/lume}"
recipient_file="${LUME_AGE_RECIPIENT_FILE:-/home/luan/.config/lume/backup.age-recipient}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="${backup_dir}/lume-${timestamp}.sql.gz.age"
temporary="${destination}.partial"

command -v age >/dev/null || { echo "age is required" >&2; exit 1; }
test -s "$recipient_file" || { echo "Missing age recipient file: $recipient_file" >&2; exit 1; }
mkdir -p "$backup_dir"
chmod 0700 "$backup_dir"
trap 'rm -f "$temporary"' EXIT

docker compose -p lume -f "${project_dir}/compose.prod.yaml" exec -T db sh -ec '
  export MYSQL_PWD="$(cat /run/secrets/root_password)"
  exec mariadb-dump --user=root --databases lume --single-transaction \
    --routines --triggers --events --hex-blob --default-character-set=utf8mb4
' | gzip -9 | age -R "$recipient_file" -o "$temporary"

test -s "$temporary"
mv "$temporary" "$destination"
sha256sum "$destination" > "${destination}.sha256"
chmod 0600 "$destination" "${destination}.sha256"
trap - EXIT

echo "Encrypted backup written to $destination"
