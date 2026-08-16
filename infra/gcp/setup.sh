#!/usr/bin/env bash
# One-time setup for Hermes on a GCP Always Free e2-micro VM (Ubuntu 24.04).
# Hermes ONLY — the 1 GB RAM e2-micro cannot host nq-trader/quantastra-agent/cron.
# Run as root (or a user with sudo):  sudo bash setup.sh
set -euo pipefail

APP_DIR="/opt/hermes"
SERVICE_USER="hermes"
HERMES_REPO="https://github.com/satyamdas03/hermes-trading.git"
API_PORT="8000"

command -v sudo >/dev/null 2>&1 || { echo "sudo is required"; exit 1; }

echo "==> Updating packages..."
sudo apt-get update && sudo apt-get upgrade -y

echo "==> Installing Python 3.12 + git + curl (no Docker — too heavy for 1 GB)..."
sudo apt-get install -y python3 python3-venv git curl ca-certificates

echo "==> Adding 2 GB swap (OOM safety net for 1 GB RAM)..."
if ! swapon --show | grep -q /swapfile; then
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo "==> Creating ${SERVICE_USER} service user..."
sudo useradd -r -m -s /bin/bash "$SERVICE_USER" || true

echo "==> Installing uv for ${SERVICE_USER}..."
sudo -u "$SERVICE_USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

echo "==> Cloning Hermes repo..."
if [[ ! -d "$APP_DIR/.git" ]]; then
    sudo -u "$SERVICE_USER" git clone "$HERMES_REPO" "$APP_DIR"
fi

echo "==> Installing Python deps (uv sync)..."
sudo -u "$SERVICE_USER" bash -c "cd '$APP_DIR' && ~/.local/bin/uv sync"

echo "==> Writing .env template (if missing)..."
if [[ ! -f "$APP_DIR/.env" ]]; then
    sudo -u "$SERVICE_USER" bash -c "cat > '$APP_DIR/.env' <<'ENV'
# Hermes trading agent environment
HERMES_TRADING_MODE=paper
HERMES_API_PORT=${API_PORT}
# Set a long random string; must match Render nq-api HERMES_API_SECRET
HERMES_API_SECRET=CHANGE_ME
# For --hermes (Claude) reflection; optional — fallback reflection works without
ANTHROPIC_API_KEY=
# Optional Kraken API keys (public data works without them)
EXCHANGE_API_KEY=
EXCHANGE_API_SECRET=
ENV"
fi

echo "==> Writing systemd unit..."
sudo tee /etc/systemd/system/hermes.service > /dev/null <<UNIT
[Unit]
Description=Hermes trading agent (paper)
After=network-online.target
Wants=network-online.target

[Service]
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=/home/${SERVICE_USER}/.local/bin/uv run python -m hermes_trading.run
Restart=always
RestartSec=10
# 1 GB RAM is tight — cap memory and let swap absorb spikes
MemoryMax=900M
MemoryHigh=700M

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable hermes

echo "==> Done."
echo "Next steps:"
echo "  1. Edit secrets:  sudo nano ${APP_DIR}/.env  (set HERMES_API_SECRET + ANTHROPIC_API_KEY)"
echo "  2. Start:         sudo systemctl start hermes"
echo "  3. Check:         sudo systemctl status hermes && journalctl -u hermes -f"
echo "  4. Open GCP firewall port ${API_PORT} (VPC network -> Firewall -> tcp:${API_PORT})"
echo "  5. Update Render nq-api: HERMES_API_URL=http://<VM_IP>:${API_PORT} and HERMES_API_SECRET"
