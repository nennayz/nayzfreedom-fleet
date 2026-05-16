#!/usr/bin/env bash
# Create a local production backup on the VPS.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/nayzfreedom}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/nayzfreedom-backups}"
SERVICE_USER="${SERVICE_USER:-nayzfreedom}"
TRAEFIK_CONFIG="${TRAEFIK_CONFIG:-/docker/traefik-fmcv/dynamic/nayzfreedom.yml}"
RETENTION="${RETENTION:-7}"
GOOGLE_DRIVE_BACKUP_FOLDER_ID="${GOOGLE_DRIVE_BACKUP_FOLDER_ID:-}"
GOOGLE_DRIVE_OAUTH_CLIENT_SECRETS="${GOOGLE_DRIVE_OAUTH_CLIENT_SECRETS:-}"
GOOGLE_DRIVE_OAUTH_TOKEN_FILE="${GOOGLE_DRIVE_OAUTH_TOKEN_FILE:-}"

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
if command -v getent >/dev/null 2>&1 && getent group "$SERVICE_USER" >/dev/null; then
    chgrp -R "$SERVICE_USER" "$BACKUP_ROOT"
    find "$BACKUP_ROOT" -type d -exec chmod 750 {} +
    find "$BACKUP_ROOT" -type f -exec chmod 640 {} +
fi

if [ -n "$GOOGLE_DRIVE_BACKUP_FOLDER_ID" ]; then
    drive_error=/tmp/nayzfreedom-drive-backup.err
    drive_args=(
        "$backup_dir/state.tgz"
        --folder-id "$GOOGLE_DRIVE_BACKUP_FOLDER_ID"
        --name "nayzfreedom-$stamp-state.tgz"
        --mime-type "application/gzip"
    )
    if [ -n "$GOOGLE_DRIVE_OAUTH_CLIENT_SECRETS" ]; then
        drive_args+=(--oauth-client-secrets "$GOOGLE_DRIVE_OAUTH_CLIENT_SECRETS")
        if [ -n "$GOOGLE_DRIVE_OAUTH_TOKEN_FILE" ]; then
            drive_args+=(--token-file "$GOOGLE_DRIVE_OAUTH_TOKEN_FILE")
        fi
    fi
    if "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/google_drive.py" "${drive_args[@]}" >/tmp/nayzfreedom-drive-backup.json 2>"$drive_error"; then
        chmod 600 /tmp/nayzfreedom-drive-backup.json
        rm -f "$drive_error"
        echo "drive_backup=uploaded"
    else
        rm -f /tmp/nayzfreedom-drive-backup.json
        echo "drive_backup=failed"
        if [ -s "$drive_error" ]; then
            chmod 600 "$drive_error"
            tail -n 1 "$drive_error" | sed "s/^/drive_backup_error=/"
        fi
    fi
fi

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | head -n "-$RETENTION" | xargs -r rm -rf

echo "backup_dir=$backup_dir"
du -sh "$backup_dir"
