"""Export demo snapshot tables from Supabase to data/demo_snapshot/*.csv.

Feeds DEMO_MODE (B3.15). Run while Supabase is live:
    python scripts/export_demo_snapshot.py
Reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from apps/api/.env.
"""
from __future__ import annotations

import csv
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "demo_snapshot"
TABLES = [
    "score_cache",
    "anjali_enrichment",
    "quantfactor_universe",
    "quarterly_test_runs",
    "quarterly_test_results",
]
PAGE = 1000


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / "apps" / "api" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def export_table(client: httpx.Client, base: str, table: str) -> int:
    rows: list[dict] = []
    offset = 0
    while True:
        r = client.get(
            f"{base}/rest/v1/{table}",
            params={"select": "*", "limit": str(PAGE), "offset": str(offset)},
        )
        if r.status_code == 404:
            print(f"  SKIP {table}: table not found")
            return 0
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    if not rows:
        print(f"  WARN {table}: 0 rows")
        return 0
    cols = sorted({k for row in rows for k in row})
    out = OUT / f"{table}.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  OK   {table}: {len(rows)} rows -> {out.relative_to(ROOT)}")
    return len(rows)


def main() -> int:
    env = load_env()
    base = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        print("Missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY in apps/api/.env")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    total = 0
    with httpx.Client(headers=headers, timeout=60) as client:
        for t in TABLES:
            total += export_table(client, base, t)
    print(f"Done. {total} total rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
