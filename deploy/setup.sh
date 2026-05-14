#!/usr/bin/env bash
# NayzFreedom VPS Setup Script
# Run once on a fresh Ubuntu/Debian server as root (or with sudo).
#
# Usage:
#   curl -sO https://raw.githubusercontent.com/nennayz/slayhack/main/deploy/setup.sh
#   chmod +x setup.sh
#   sudo ./setup.sh
#
# What it does:
#   1. Installs system dependencies (python3, git, nginx optional)
#   2. Creates a dedicated system user (nayzfreedom)
#   3. Clones the repo to /opt/nayzfreedom
#   4. Creates a venv and installs requirements
#   5. Copies .env.example → /opt/nayzfreedom/.env (you fill in keys after)
#   6. Installs systemd units for dashboard, scheduler, reporter
#   7. Enables and starts the dashboard service

set -euo pipefail

REPO_URL="git@github.com:nennayz/slayhack.git"
INSTALL_DIR="/opt/nayzfreedom"
SERVICE_USER="nayzfreedom"
PYTHON="python3"

echo "=== NayzFreedom VPS Setup ==="

# ── 1. System deps ──────────────────────────────────────────────────────────
echo "[1/6] Installing system packages..."
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip git

# ── 2. Create service user ───────────────────────────────────────────────────
echo "[2/6] Creating system user '$SERVICE_USER'..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home "$INSTALL_DIR" --create-home "$SERVICE_USER"
fi

# ── 3. Clone / update repo ───────────────────────────────────────────────────
echo "[3/6] Cloning repo to $INSTALL_DIR..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Repo already exists — pulling latest..."
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" pull
else
    # If using SSH key auth, copy your deploy key first:
    #   ssh-keygen -t ed25519 -C "nayzfreedom-deploy" -f /home/nayzfreedom/.ssh/id_ed25519
    #   cat /home/nayzfreedom/.ssh/id_ed25519.pub  → add as Deploy Key on GitHub
    sudo -u "$SERVICE_USER" git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ── 4. Python venv + requirements ────────────────────────────────────────────
echo "[4/6] Setting up Python venv..."
sudo -u "$SERVICE_USER" $PYTHON -m venv "$INSTALL_DIR/.venv"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── 5. .env file ─────────────────────────────────────────────────────────────
echo "[5/6] Creating .env..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    echo ""
    echo "  *** ACTION REQUIRED ***"
    echo "  Edit $INSTALL_DIR/.env and fill in your API keys before starting."
    echo "  nano $INSTALL_DIR/.env"
    echo ""
else
    echo "  .env already exists — skipping."
fi

# ── 6. Install + enable systemd units ────────────────────────────────────────
echo "[6/6] Installing systemd units..."
DEPLOY_DIR="$(dirname "$0")"

for unit in \
    nayzfreedom-dashboard.service \
    nayzfreedom-scheduler.service \
    nayzfreedom-scheduler.timer \
    nayzfreedom-reporter.service \
    nayzfreedom-reporter.timer; do
    cp "$DEPLOY_DIR/$unit" "/etc/systemd/system/$unit"
done

systemctl daemon-reload

# Dashboard runs persistently
systemctl enable --now nayzfreedom-dashboard.service

# Scheduler + reporter run via timers
systemctl enable --now nayzfreedom-scheduler.timer
systemctl enable --now nayzfreedom-reporter.timer

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Fill in API keys:  nano $INSTALL_DIR/.env"
echo "  2. Restart dashboard: systemctl restart nayzfreedom-dashboard"
echo "  3. Check dashboard:   systemctl status nayzfreedom-dashboard"
echo "  4. View logs:         journalctl -u nayzfreedom-dashboard -f"
echo "  5. Dashboard URL:     http://<your-server-ip>:8000"
echo "     (Set DASHBOARD_USER / DASHBOARD_PASSWORD in .env for auth)"
echo ""
echo "Timers scheduled:"
echo "  Scheduler: daily at 06:00 UTC"
echo "  Reporter:  every Monday at 08:00 UTC"
echo "  Check with: systemctl list-timers | grep nayz"
