#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 BACKUP.sql.gz.age" >&2
  exit 2
fi

backup="$(realpath "$1")"
identity_file="${LUME_AGE_IDENTITY_FILE:-/home/luan/.config/lume/backup.age-key}"
api_image="${LUME_API_IMAGE:-lume-api:local}"
drill_id="lume-restore-$(date -u +%Y%m%d%H%M%S)-$$"
db_name="${drill_id}-db"
api_name="${drill_id}-api"
network_name="${drill_id}-network"
volume_name="${drill_id}-data"
private_dir="$(mktemp -d)"

cleanup() {
  docker rm -f "$api_name" "$db_name" >/dev/null 2>&1 || true
  docker volume rm "$volume_name" >/dev/null 2>&1 || true
  docker network rm "$network_name" >/dev/null 2>&1 || true
  rm -rf "$private_dir"
}
trap cleanup EXIT
umask 077

command -v age >/dev/null || { echo "age is required" >&2; exit 1; }
test -s "$backup" || { echo "Backup is missing or empty: $backup" >&2; exit 1; }
test -s "$identity_file" || { echo "Missing age identity: $identity_file" >&2; exit 1; }
if [[ -f "${backup}.sha256" ]]; then
  (cd "$(dirname "$backup")" && sha256sum -c "$(basename "${backup}.sha256")")
fi

openssl rand -hex 32 > "${private_dir}/root_password"
openssl rand -hex 32 > "${private_dir}/app_password"
openssl rand -hex 48 > "${private_dir}/session_secret"

docker network create --internal "$network_name" >/dev/null
docker volume create "$volume_name" >/dev/null
docker run -d --name "$db_name" --network "$network_name" --network-alias db \
  -e MARIADB_DATABASE=lume \
  -e MARIADB_USER=lume_app \
  -e MARIADB_PASSWORD_FILE=/run/secrets/app_password \
  -e MARIADB_ROOT_PASSWORD_FILE=/run/secrets/root_password \
  -v "${private_dir}/app_password:/run/secrets/app_password:ro" \
  -v "${private_dir}/root_password:/run/secrets/root_password:ro" \
  -v "${volume_name}:/var/lib/mysql" \
  --health-cmd='healthcheck.sh --connect --innodb_initialized' \
  --health-interval=2s --health-timeout=3s --health-retries=30 \
  mariadb:11.4.13 >/dev/null

for _ in $(seq 1 45); do
  [[ "$(docker inspect -f '{{.State.Health.Status}}' "$db_name")" == "healthy" ]] && break
  sleep 2
done
[[ "$(docker inspect -f '{{.State.Health.Status}}' "$db_name")" == "healthy" ]] || {
  docker logs "$db_name" >&2
  exit 1
}

age --decrypt -i "$identity_file" "$backup" | gzip -dc | docker exec -i "$db_name" sh -ec '
  export MYSQL_PWD="$(cat /run/secrets/root_password)"
  exec mariadb --user=root
'

docker run -d --name "$api_name" --network "$network_name" --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m,mode=1777 \
  -e LUME_ENV=production \
  -e LUME_DATABASE_HOST=db \
  -e LUME_DATABASE_NAME=lume \
  -e LUME_DATABASE_USER=lume_app \
  -e LUME_DATABASE_PASSWORD_FILE=/run/secrets/app_password \
  -e LUME_SESSION_SECRET_FILE=/run/secrets/session_secret \
  -v "${private_dir}/app_password:/run/secrets/app_password:ro" \
  -v "${private_dir}/session_secret:/run/secrets/session_secret:ro" \
  "$api_image" >/dev/null

for _ in $(seq 1 30); do
  if docker exec "$api_name" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2)" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker exec "$api_name" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2)" >/dev/null

docker exec "$db_name" sh -ec '
  export MYSQL_PWD="$(cat /run/secrets/root_password)"
  mariadb --user=root --batch --skip-column-names lume -e \
    "SELECT CONCAT(table_name, CHAR(9), table_rows) FROM information_schema.tables WHERE table_schema = '\''lume'\'' ORDER BY table_name"
'

echo "Restore verification passed for $backup"
