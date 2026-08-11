#!/usr/bin/env bash
# Migrate Hermes state from local submodule (or a Railway volume dump) into the
# Oracle Cloud VM's Docker volume before starting Hermes.
set -euo pipefail

APP_DIR="/opt/neuralquant"
HERMES_STATE_SRC="${HERMES_STATE_SRC:-$APP_DIR/hermes-trading/state}"

echo "==> Hermes state migration"
echo "    Source: $HERMES_STATE_SRC"

if [[ ! -d "$HERMES_STATE_SRC" ]]; then
    echo "ERROR: Source directory does not exist: $HERMES_STATE_SRC"
    echo "Hermes will start with an empty state volume and re-learn from scratch."
    exit 1
fi

# Ensure the Docker volume exists (Hermes service creates it on first run, but
# we can also create a temp container to seed it).
echo "==> Seeding hermes_state Docker volume..."
cd "$APP_DIR/infra/oracle-cloud"

# Create a one-off container that copies local state into the named volume.
docker compose run --rm --entrypoint '' hermes \
    bash -c "mkdir -p /app/state && cp -a /src-state/* /app/state/" \
    || true

# Fallback: use a plain alpine container to copy if compose service is not built yet.
if ! docker compose ps hermes >/dev/null 2>&1; then
    docker run --rm \
        -v "$HERMES_STATE_SRC:/src-state:ro" \
        -v "${APP_DIR}_hermes_state:/dst" \
        alpine:latest \
        sh -c "mkdir -p /dst && cp -a /src-state/* /dst/"
fi

echo "==> Done. Hermes state volume seeded from $HERMES_STATE_SRC"
echo "    To use a Railway volume export instead, set HERMES_STATE_SRC to the"
echo "    extracted Railway /app/state directory before running this script."
