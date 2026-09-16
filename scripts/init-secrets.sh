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
  # Compose implements file-backed secrets as bind mounts and cannot remap
  # their ownership. The containing host directory remains 0700; 0444 lets
  # the unprivileged users inside the relevant containers read the mount.
  chmod 0444 "$path"
  echo "Created $path"
done

# Normalize files created by an earlier version of this script as well.
chmod 0444 \
  "${secrets_dir}/app_password" \
  "${secrets_dir}/migrator_password" \
  "${secrets_dir}/root_password" \
  "${secrets_dir}/session_secret"

echo "Create an age identity separately, keep its private key off-host, and place only its recipient in ${secrets_dir}/backup.age-recipient."
