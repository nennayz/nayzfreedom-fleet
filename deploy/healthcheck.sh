#!/usr/bin/env bash
# Fail fast when the production VPS is unhealthy.

set -euo pipefail

HEALTH_URL="${HEALTH_URL:-https://fleet.nayzfreedom.cloud/healthz}"
DISK_PATH="${DISK_PATH:-/opt/nayzfreedom}"
DISK_LIMIT="${DISK_LIMIT:-85}"
ERROR_WINDOW="${ERROR_WINDOW:-15 minutes ago}"

check_unit() {
    local unit="$1"
    systemctl is-active --quiet "$unit"
    echo "unit_ok=$unit"
}

curl -fsS "$HEALTH_URL" >/dev/null
echo "health_url_ok=$HEALTH_URL"

check_unit nayzfreedom-dashboard.service
check_unit nayzfreedom-bot.service
check_unit nayzfreedom-scheduler.timer
check_unit nayzfreedom-reporter.timer

disk_used="$(df -P "$DISK_PATH" | awk 'NR == 2 {gsub("%", "", $5); print $5}')"
if [ "$disk_used" -ge "$DISK_LIMIT" ]; then
    echo "disk_used_percent=$disk_used limit=$DISK_LIMIT"
    exit 1
fi
echo "disk_ok_percent=$disk_used"

for unit in \
    nayzfreedom-dashboard.service \
    nayzfreedom-bot.service \
    nayzfreedom-scheduler.service \
    nayzfreedom-reporter.service; do
    hits="$(journalctl -u "$unit" --since "$ERROR_WINDOW" --no-pager 2>/dev/null | { grep -E "Traceback|ERROR|CRITICAL" || true; } | wc -l | tr -d " ")"
    if [ "$hits" != "0" ]; then
        echo "recent_error_hits=$unit:$hits"
        exit 1
    fi
    echo "recent_errors_ok=$unit"
done
