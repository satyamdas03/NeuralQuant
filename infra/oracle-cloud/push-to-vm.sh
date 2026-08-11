#!/usr/bin/env bash
# Push the local Oracle Cloud deployment kit to a provisioned Oracle VM.
# Usage:
#   export ORACLE_VM_USER=ubuntu
#   export ORACLE_VM_IP=203.0.113.10
#   ./infra/oracle-cloud/push-to-vm.sh
set -euo pipefail

ORACLE_VM_USER="${ORACLE_VM_USER:-ubuntu}"
ORACLE_VM_IP="${ORACLE_VM_IP:-}"
APP_DIR="/opt/neuralquant"

if [[ -z "$ORACLE_VM_IP" ]]; then
    echo "ERROR: set ORACLE_VM_IP environment variable" >&2
    exit 1
fi

LOCAL_KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$LOCAL_KIT_DIR/../.." && pwd)"

echo "==> Pushing Oracle Cloud kit + submodules to $ORACLE_VM_USER@$ORACLE_VM_IP..."

# Ensure Hermes submodule is initialized locally before push.
git -C "$REPO_ROOT" submodule update --init --recursive

# Sync only the deployment-relevant files to keep the push small.
rsync -avz --delete \
    -e "ssh -o StrictHostKeyChecking=no" \
    "$REPO_ROOT/infra/oracle-cloud/" \
    "$REPO_ROOT/hermes-trading/" \
    "$REPO_ROOT/scripts/cron_invoke.py" \
    "$REPO_ROOT/pyproject.toml" \
    "$REPO_ROOT/uv.lock" \
    "$REPO_ROOT/apps/api/" \
    "$REPO_ROOT/packages/" \
    "$REPO_ROOT/trade_daemon.py" \
    "$ORACLE_VM_USER@$ORACLE_VM_IP:$APP_DIR/"

echo "==> Remote files synced."
echo "Next: SSH in and run: sudo bash $APP_DIR/infra/oracle-cloud/setup.sh"
