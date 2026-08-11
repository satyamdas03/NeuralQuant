#!/usr/bin/env bash
# One-time setup script for NeuralQuant on an Oracle Cloud Free Tier ARM instance.
# Run as root or a user with sudo on Ubuntu 22.04/24.04 ARM.
set -euo pipefail

APP_DIR="/opt/neuralquant"

echo "==> Updating packages..."
sudo apt-get update && sudo apt-get upgrade -y

echo "==> Installing Docker..."
# Install Docker Engine
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Adding current user to docker group..."
sudo usermod -aG docker "$USER" || true

echo "==> Creating app directory..."
sudo mkdir -p "$APP_DIR"
sudo chown "$USER:$USER" "$APP_DIR"

echo "==> Adding 4 GB swap (helpful for ARM builds with 12 GB RAM)..."
if ! swapon --show | grep -q /swapfile; then
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo "==> Done."
echo "Next steps:"
echo "  1. Log out and back in (or run 'newgrp docker') so docker group takes effect."
echo "  2. Clone the repo: git clone https://github.com/satyamdas03/NeuralQuant.git $APP_DIR"
echo "  3. Copy $APP_DIR/infra/oracle-cloud/.env.example to $APP_DIR/infra/oracle-cloud/.env and fill values."
echo "  4. cd $APP_DIR/infra/oracle-cloud && docker compose up -d --build"
echo "  5. Open Oracle firewall ports 80/443 and optionally point a domain A-record at this VM's public IP."
