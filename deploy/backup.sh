#!/usr/bin/env bash
# Create a local production backup on the VPS.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/nayzfreedom}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/nayzfreedom-backups}"
TRAEFIK_CONFIG="${TRAEFIK_CONFIG:-/docker/traefik-fmcv/dynamic/nayzfreedom.yml}"
RETENTION="${RETENTION:-7}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$BACKUP_ROOT/$stamp"

mkdir -p "$backup_dir"
chmod 700 "$BACKUP_ROOT" "$backup_dir"

cd "$INSTALL_DIR"

tar -czf "$backup_dir/state.tgz" .env projects output logs

if [ -f "$TRAEFIK_CONFIG" ]; then
    mkdir -p "$backup_dir/traefik"
    cp "$TRAEFIK_CONFIG" "$backup_dir/traefik/nayzfreedom.yml"
fi

sha256sum "$backup_dir/state.tgz" > "$backup_dir/state.tgz.sha256"
chmod -R go-rwx "$backup_dir"

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | head -n "-$RETENTION" | xargs -r rm -rf

echo "backup_dir=$backup_dir"
du -sh "$backup_dir"
