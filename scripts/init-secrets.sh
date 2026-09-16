#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
secrets_dir="${LUME_SECRETS_DIR:-/home/luan/.config/lume}"
mkdir -p "$secrets_dir"
chmod 0700 "$secrets_dir"

for name in app_password migrator_password root_password session_secret; do
  path="${secrets_dir}/${name}"
  if [[ -e "$path" ]]; then
    echo "Keeping existing $path"
    continue
  fi
  openssl rand -hex 48 > "$path"
  chmod 0600 "$path"
  echo "Created $path"
done

echo "Create an age identity separately, keep its private key off-host, and place only its recipient in ${secrets_dir}/backup.age-recipient."
