#!/bin/sh
set -e

migrator_password="$(cat /run/secrets/migrator_password)"
case "$migrator_password" in
  *"'"*) echo "Migrator password must not contain a single quote" >&2; exit 1 ;;
esac

docker_process_sql <<SQL
CREATE USER IF NOT EXISTS 'lume_migrator'@'%' IDENTIFIED BY '${migrator_password}';
GRANT ALL PRIVILEGES ON lume.* TO 'lume_migrator'@'%';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'lume_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON lume.* TO 'lume_app'@'%';
FLUSH PRIVILEGES;
SQL
