#!/usr/bin/env bash
# Pull latest code and restart services.
# Run on the VPS as root (or with sudo) whenever you push changes.
#
# Usage: sudo ./update.sh

set -euo pipefail

INSTALL_DIR="/opt/nayzfreedom"
SERVICE_USER="nayzfreedom"

echo "=== NayzFreedom Update ==="

echo "[1/3] Pulling latest code..."
sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" pull

echo "[2/3] Installing dependencies..."
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

echo "[3/3] Restarting services..."
systemctl restart nayzfreedom-dashboard.service
systemctl status nayzfreedom-dashboard.service --no-pager
systemctl restart nayzfreedom-bot.service
systemctl status nayzfreedom-bot.service --no-pager

echo ""
echo "Done. Services are running."
echo "Dashboard logs: journalctl -u nayzfreedom-dashboard -f"
echo "Bot logs:       journalctl -u nayzfreedom-bot -f"
