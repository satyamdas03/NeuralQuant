#!/usr/bin/env bash
# Delete the Railway Hermes project and all its resources after migration to Oracle.
# WARNING: destructive. Only run after Hermes is live on Oracle and verified.
set -euo pipefail

PROJECT_NAME="zonal-curiosity"

read -r -p "Hermes is live on Oracle and verified? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Aborted."
    exit 1
fi

echo "==> Linking to Railway project: $PROJECT_NAME"
railway link -p "$PROJECT_NAME"

echo "==> Stopping service..."
railway down || true

echo "==> Deleting volume..."
volume_id=$(railway volume list --json 2>/dev/null | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [[ -n "$volume_id" ]]; then
    railway volume delete --volume "$volume_id" --yes
else
    echo "No volume found."
fi

echo "==> Deleting project..."
railway project delete --yes || true

echo "==> Done."
echo "To close the Railway account entirely, visit https://railway.com/settings/billing"
echo "and cancel any subscription / delete the account."
