#!/usr/bin/env bash
# Verify the latest production backup archive can be listed and contains core state.

set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/opt/nayzfreedom-backups}"

latest_dir="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"
if [ -z "$latest_dir" ]; then
    echo "restore_smoke=no_backups"
    exit 1
fi

archive="$latest_dir/state.tgz"
checksum="$latest_dir/state.tgz.sha256"

test -f "$archive"
test -f "$checksum"

(
    cd "$latest_dir"
    sha256sum -c state.tgz.sha256 >/dev/null
)

listing="$(mktemp)"
trap 'rm -f "$listing"' EXIT
tar -tzf "$archive" > "$listing"

grep -q '^\.env$' "$listing"
grep -q '^projects/' "$listing"
grep -q '^output/' "$listing"
grep -q '^logs/' "$listing"

echo "restore_smoke=ok archive=$archive"
