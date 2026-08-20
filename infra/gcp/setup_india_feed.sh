#!/usr/bin/env bash
# One-time setup for the autonomous India price feeder on the GCP e2-micro VM.
# Run as root (or a user with sudo):  sudo bash setup_india_feed.sh
set -euo pipefail

APP_DIR="/opt/neuralquant"
VENV_DIR="${APP_DIR}/venv"
REPO="https://github.com/satyamdas03/NeuralQuant.git"
FEED_SCRIPT="${APP_DIR}/infra/gcp/india_feed.py"
LOG_FILE="/var/log/india_feed.log"

command -v sudo >/dev/null 2>&1 || { echo "sudo is required"; exit 1; }

echo "==> Installing system deps (git, python3-venv, cron)..."
sudo apt-get update
sudo apt-get install -y git python3 python3-venv cron ca-certificates

# Ensure cron daemon is running
sudo systemctl enable cron || true
sudo systemctl start cron || true

echo "==> Creating application directory ${APP_DIR}..."
sudo mkdir -p "${APP_DIR}"

# If the repo is already present, pull; otherwise shallow-clone to keep disk use low.
if [[ -d "${APP_DIR}/.git" ]]; then
    echo "==> NeuralQuant repo exists — pulling latest..."
    sudo -u hermes bash -c "cd '${APP_DIR}' && git pull origin main" || true
else
    echo "==> Cloning NeuralQuant repo (shallow, single branch)..."
    # Use a non-root owner if hermes user exists (created by Hermes setup), otherwise root.
    SERVICE_USER="hermes"
    if id "${SERVICE_USER}" &>/dev/null; then
        sudo git clone --depth 1 --single-branch --branch main "${REPO}" "${APP_DIR}"
        sudo chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"
    else
        sudo git clone --depth 1 --single-branch --branch main "${REPO}" "${APP_DIR}"
    fi
fi

echo "==> Creating Python virtual environment..."
if [[ ! -d "${VENV_DIR}" ]]; then
    sudo python3 -m venv "${VENV_DIR}"
fi

# Upgrade pip/setuptools to avoid yfinance install issues.
sudo "${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel

echo "==> Installing feeder dependencies (lightweight subset)..."
sudo "${VENV_DIR}/bin/pip" install --no-cache-dir \
    "yfinance>=1.3.0,<1.4.0" \
    "curl_cffi>=0.7.0" \
    "pandas>=2.2.0" \
    "numpy>=1.26.0" \
    "httpx>=0.27.0" \
    "python-dotenv>=1.0.0"

echo "==> Writing .env template..."
if [[ ! -f "${APP_DIR}/apps/api/.env" ]]; then
    sudo mkdir -p "${APP_DIR}/apps/api"
    sudo tee "${APP_DIR}/apps/api/.env" > /dev/null <<'ENV'
# Supabase credentials — required for the India feeder to write stock_snapshot.
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
ENV
    echo "!!! Please edit ${APP_DIR}/apps/api/.env and add your Supabase credentials !!!"
fi

echo "==> Setting up log file..."
sudo touch "${LOG_FILE}"
sudo chmod 644 "${LOG_FILE}"

echo "==> Installing cron job (every 15 min, Indian market hours)..."
CRON_LINE="*/15 3-10 * * 1-5 ${VENV_DIR}/bin/python ${FEED_SCRIPT} >> ${LOG_FILE} 2>&1"
# Remove any existing india_feed cron line, then add the new one.
( sudo crontab -l 2>/dev/null | grep -v 'infra/gcp/india_feed.py' || true ) | sudo crontab -
( sudo crontab -l 2>/dev/null; echo "${CRON_LINE}" ) | sudo crontab -

echo "==> Setup complete."
echo "Next steps:"
echo "  1. Edit secrets:  sudo nano ${APP_DIR}/apps/api/.env"
echo "  2. Run once:      sudo ${VENV_DIR}/bin/python ${FEED_SCRIPT}"
echo "  3. Check logs:    sudo tail -f ${LOG_FILE}"
echo "  4. Verify live:   curl https://neuralquant.onrender.com/stocks/TCS.NS?market=IN"
