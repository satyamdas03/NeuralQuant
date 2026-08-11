#!/usr/bin/env bash
# One-time setup script for NeuralQuant on an Oracle Cloud Free Tier ARM instance.
# Run as root or a user with sudo on Ubuntu 22.04/24.04 ARM.
# This provisions the "now + safe" stack: Hermes + nq-trader + quantastra-agent + cron jobs.
set -euo pipefail

APP_DIR="/opt/neuralquant"
SERVICE_USER="neuralquant"

command -v sudo >/dev/null 2>&1 || { echo "sudo is required"; exit 1; }

echo "==> Updating packages..."
sudo apt-get update && sudo apt-get upgrade -y

echo "==> Installing Docker..."
sudo apt-get install -y ca-certificates curl gnupg cron
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "==> Adding ${SERVICE_USER} service user..."
sudo useradd -r -s /bin/bash -d "$APP_DIR" -m "$SERVICE_USER" || true
sudo usermod -aG docker "$SERVICE_USER" || true
sudo usermod -aG docker "$USER" || true

echo "==> Creating app directory..."
sudo mkdir -p "$APP_DIR"
sudo chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

echo "==> Adding 4 GB swap (helpful for ARM builds with 12 GB RAM)..."
if ! swapon --show | grep -q /swapfile; then
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo "==> Cloning repository..."
if [[ ! -d "$APP_DIR/.git" ]]; then
    sudo -u "$SERVICE_USER" git clone https://github.com/satyamdas03/NeuralQuant.git "$APP_DIR"
fi

echo "==> Initializing Hermes submodule..."
sudo -u "$SERVICE_USER" bash -c "cd '$APP_DIR' && git submodule update --init --recursive"

echo "==> Installing crontab for ${SERVICE_USER}..."
sudo -u "$SERVICE_USER" crontab "$APP_DIR/infra/oracle-cloud/crontab.txt"

echo "==> Done."
echo "Next steps:"
echo "  1. Log out and back in (or run 'newgrp docker') so docker group takes effect."
echo "  2. Copy $APP_DIR/infra/oracle-cloud/.env.example to $APP_DIR/infra/oracle-cloud/.env and fill values."
echo "  3. (Optional) Copy Hermes state into $APP_DIR/hermes-trading/state/ if migrating from Railway."
echo "  4. cd $APP_DIR/infra/oracle-cloud && docker compose up -d --build"
echo "  5. Open Oracle firewall ports 80/443 and optionally point a domain A-record at this VM's public IP."
echo "  6. Update Render nq-api env vars HERMES_API_URL and HERMES_API_SECRET to point here."
