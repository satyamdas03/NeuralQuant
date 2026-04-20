"""Authed smoke test — creates test user via service role, logs in, hits every
auth-gated endpoint. Run after health_check.py passes.

Env required:
  SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY (from apps/api/.env)

Usage: python scripts/authed_smoke.py [--base https://neuralquant.onrender.com]
Exit 0 iff all authed checks pass.
"""
from __future__ import annotations
import argparse
import os
import sys
import time
import uuid
from pathlib import Path

import requests

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def _load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://neuralquant.onrender.com")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    env = _load_env(Path("apps/api/.env"))
    sb_url = os.getenv("SUPABASE_URL") or env.get("SUPABASE_URL")
    anon = os.getenv("SUPABASE_ANON_KEY") or env.get("SUPABASE_ANON_KEY")
    service = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (sb_url and anon and service):
        print("Missing SUPABASE env vars")
        return 2

    # Create ephemeral test user via admin API
    email = f"smoke+{uuid.uuid4().hex[:10]}@example.com"
    password = "Smoke-Test-" + uuid.uuid4().hex[:12]
    print(f"\nAuthed smoke — {base}\nTest user: {email}\n")

    r = requests.post(
        f"{sb_url}/auth/v1/admin/users",
        headers={"apikey": service, "Authorization": f"Bearer {service}"},
        json={"email": email, "password": password, "email_confirm": True},
        timeout=30,
    )
    if r.status_code not in (200, 201):
        print(f"{FAIL} admin create user: {r.status_code} {r.text[:200]}")
        return 1
    user_id = r.json().get("id")
    print(f"  created user id={user_id}")

    # Password grant → access token
    r = requests.post(
        f"{sb_url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"{FAIL} password grant: {r.status_code} {r.text[:200]}")
        return 1
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    print(f"  token acquired\n")

    fails = 0
    total = 0

    def hit(name: str, method: str, path: str, body=None, expect=(200,)):
        nonlocal fails, total
        total += 1
        t0 = time.time()
        try:
            r = requests.request(
                method, f"{base}{path}", headers=auth, json=body, timeout=90
            )
            el = time.time() - t0
            ok = r.status_code in expect
            try:
                payload = r.json()
            except Exception:
                payload = r.text[:120]
        except Exception as exc:
            el = time.time() - t0
            ok, r_status, payload = False, 0, str(exc)
            tag = FAIL
            print(f"{name}\n  {tag}  [{r_status:>3}] {el*1000:6.0f}ms  {payload}")
            fails += 1
            return None
        tag = PASS if ok else FAIL
        note = ""
        if isinstance(payload, dict):
            if "detail" in payload and not ok:
                note = str(payload["detail"])[:100]
            elif "results" in payload:
                note = f"{len(payload['results'])} results"
            elif "equity" in payload:
                note = f"{len(payload.get('equity', []))} equity pts · sharpe={payload.get('sharpe')}"
            elif "answer" in payload:
                note = f"answer len={len(str(payload['answer']))}"
            elif "items" in payload:
                note = f"{len(payload['items'])} items"
            elif "email" in payload:
                note = f"email={payload['email']}"
        print(f"{name}\n  {tag}  [{r.status_code:>3}] {el*1000:6.0f}ms  {note}")
        if not ok:
            fails += 1
        return payload

    # --- profile ---
    hit("GET /auth/me", "GET", "/auth/me")

    # --- watchlist add/list/remove ---
    added = hit("POST /watchlist (AAPL)", "POST", "/watchlist",
                {"ticker": "AAPL", "market": "US"}, expect=(201,))
    hit("GET /watchlist", "GET", "/watchlist")
    if isinstance(added, dict) and added.get("id"):
        hit(f"DELETE /watchlist/{added['id'][:8]}", "DELETE",
            f"/watchlist/{added['id']}", expect=(204,))

    # --- screener (tier quota) ---
    hit("POST /screener", "POST", "/screener",
        {"market": "US", "max_results": 5})

    # --- query (Claude-backed) ---
    hit("POST /query", "POST", "/query",
        {"question": "Is the S&P 500 bullish?"})

    # --- backtest ---
    hit("POST /backtest", "POST", "/backtest",
        {"ticker": "AAPL", "market": "US", "fast": 20, "slow": 50, "period": "1y"})

    # --- cleanup: delete test user ---
    try:
        requests.delete(
            f"{sb_url}/auth/v1/admin/users/{user_id}",
            headers={"apikey": service, "Authorization": f"Bearer {service}"},
            timeout=30,
        )
        print(f"\n  cleaned up test user")
    except Exception as e:
        print(f"\n  cleanup failed: {e}")

    print(f"\n{'='*60}")
    if fails == 0:
        print(f"{PASS}  {total}/{total} authed checks passed")
        return 0
    print(f"{FAIL}  {fails}/{total} authed checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
