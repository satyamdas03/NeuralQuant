#!/usr/bin/env bash
# Update Hermes to latest main and restart. Run as root:  sudo bash deploy.sh
set -euo pipefail

APP_DIR="/opt/hermes"
SERVICE_USER="hermes"

echo "==> Pulling latest Hermes..."
sudo -u "$SERVICE_USER" bash -c "cd '$APP_DIR' && git pull origin main"

echo "==> Syncing deps..."
sudo -u "$SERVICE_USER" bash -c "cd '$APP_DIR' && ~/.local/bin/uv sync"

echo "==> Restarting Hermes..."
sudo systemctl restart hermes

echo "==> Done. Status:"
sudo systemctl --no-pager status hermes --lines=5
