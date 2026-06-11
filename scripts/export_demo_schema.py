"""Dump CREATE TABLE DDL for the demo-snapshot tables from live Supabase.

Uses the PostgREST OpenAPI spec (the direct db.* host is IPv6-only and often
unreachable). Produces docker/initdb/001_demo_schema.sql for the docker-compose
demo stack. Run while Supabase is live:
    python scripts/export_demo_schema.py
"""
from __future__ import annotations

import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docker" / "initdb" / "001_demo_schema.sql"
TABLES = [
    # Seeded from data/demo_snapshot CSVs
    "score_cache",
    "anjali_enrichment",
    "quantfactor_universe",
    "quarterly_test_runs",
    "quarterly_test_results",
    # Empty but required — the API reads/writes these at runtime
    "score_cache_history",
    "stock_meta",
    "stock_snapshot",
    "enrichment_cache",
    "usage_log",
    "user_events",
    "conversations",
    "watchlists",
    "users",
    "shared_analyses",
    "agent_logs",
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / "apps" / "api" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def main() -> int:
    env = load_env()
    base = env["SUPABASE_URL"].rstrip("/")
    key = env["SUPABASE_SERVICE_ROLE_KEY"]
    r = httpx.get(f"{base}/rest/v1/",
                  headers={"apikey": key, "Authorization": f"Bearer {key}"},
                  timeout=30)
    r.raise_for_status()
    defs = r.json().get("definitions", {})
    parts = ["-- Auto-generated from live Supabase PostgREST spec. Demo stack only.\n"]
    for t in TABLES:
        props = defs.get(t, {}).get("properties", {})
        if not props:
            print(f"  SKIP {t}: not in spec")
            continue
        cols = []
        for name, meta in props.items():
            pgtype = meta.get("format", "text").split("(")[0] or "text"
            # Native arrays load as jsonb in the demo stack: the snapshot CSVs
            # store them as JSON, and PostgREST serves both identically.
            if pgtype.endswith("[]"):
                pgtype = "jsonb"
            cols.append(f'    "{name}" {pgtype}')
        parts.append(f'CREATE TABLE IF NOT EXISTS "{t}" (\n' + ",\n".join(cols) + "\n);\n")
        print(f"  OK   {t}: {len(props)} columns")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
