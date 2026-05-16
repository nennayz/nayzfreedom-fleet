#!/usr/bin/env bash
# Pull latest code and restart services.
# Run on the VPS as root (or with sudo) whenever you push changes.
#
# Usage: sudo ./update.sh

set -euo pipefail

INSTALL_DIR="/opt/nayzfreedom"
SERVICE_USER="nayzfreedom"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

echo "=== NayzFreedom Update ==="

echo "[1/3] Pulling latest code..."
sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" fetch origin "$DEPLOY_BRANCH"
current_branch="$(sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" branch --show-current)"
if [ "$current_branch" != "$DEPLOY_BRANCH" ]; then
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" switch "$DEPLOY_BRANCH"
fi
sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" pull --ff-only origin "$DEPLOY_BRANCH"

echo "[2/3] Installing dependencies..."
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

echo "[3/3] Restarting services..."
systemctl daemon-reload
systemctl restart nayzfreedom-dashboard.service
systemctl status nayzfreedom-dashboard.service --no-pager
systemctl restart nayzfreedom-bot.service
systemctl status nayzfreedom-bot.service --no-pager
systemctl restart nayzfreedom-healthcheck.timer

echo ""
echo "Done. Services are running."
echo "Dashboard logs: journalctl -u nayzfreedom-dashboard -f"
echo "Bot logs:       journalctl -u nayzfreedom-bot -f"
