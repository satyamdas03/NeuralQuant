#!/usr/bin/env bash
# Post-migration health checks for the Oracle Cloud VM.
# Run locally or on the VM after `docker compose up`.
set -euo pipefail

VM_IP="${1:-}"
if [[ -z "$VM_IP" ]]; then
    echo "Usage: $0 <VM_PUBLIC_IP>" >&2
    exit 1
fi

FAIL=0

check() {
    local name="$1"
    local url="$2"
    local want="$3"
    echo -n "==> $name ... "
    if body=$(curl -fsS "$url" 2>/dev/null); then
        if echo "$body" | grep -q "$want"; then
            echo "OK"
        else
            echo "FAIL (expected '$want' in $body)"
            FAIL=1
        fi
    else
        echo "FAIL (curl error)"
        FAIL=1
    fi
}

check "VM health" "http://$VM_IP/health" "ok"
check "Hermes health" "http://$VM_IP/hermes/health" "ok\|healthy\|status"
check "Hermes status" "http://$VM_IP/hermes/status" "mode\|status\|balance"
check "Hermes strategy" "http://$VM_IP/hermes/strategy" "strategy\|version"

echo "==> Docker compose status:"
ssh "${ORACLE_VM_USER:-ubuntu}@$VM_IP" "cd /opt/neuralquant/infra/oracle-cloud && docker compose ps"

echo "==> Recent logs (tail 20):"
ssh "${ORACLE_VM_USER:-ubuntu}@$VM_IP" "cd /opt/neuralquant/infra/oracle-cloud && docker compose logs --tail 20 hermes nq-trader quantastra-agent"

if [[ "$FAIL" -eq 0 ]]; then
    echo "==> All health checks passed."
else
    echo "==> Some health checks failed." >&2
    exit 1
fi
