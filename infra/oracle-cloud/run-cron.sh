#!/usr/bin/env bash
# Wrapper used by crontab on the Oracle Cloud VM.
# Loads /opt/neuralquant/.env then invokes the Render nq-api cron endpoint.
set -euo pipefail

APP_DIR="/opt/neuralquant"
ENDPOINT="${1:-}"
PARAMS="${2:-}"

if [[ -z "$ENDPOINT" ]]; then
    echo "Usage: $0 <endpoint> [params]" >&2
    exit 1
fi

# Load env file if present
if [[ -f "$APP_DIR/infra/oracle-cloud/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$APP_DIR/infra/oracle-cloud/.env"
    set +a
fi

cd "$APP_DIR"

# Use uv from PATH or fallback to ~/.local/bin/uv
UV_BIN="$(command -v uv || echo "$HOME/.local/bin/uv")"

exec "$UV_BIN" run python scripts/cron_invoke.py \
    --endpoint "$ENDPOINT" \
    ${PARAMS:+--params "$PARAMS"}
