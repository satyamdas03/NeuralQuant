# apps/api/src/nq_api/db_migrate.py
"""Lightweight migration check at startup.

Checks that required tables exist and logs warnings if not.
Actual DDL must be applied via Supabase SQL editor or direct DB connection.
"""
import logging

log = logging.getLogger(__name__)


async def run_pending():
    """Check if required tables exist. Log warnings for missing ones."""
    import os
    import httpx

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not supabase_key:
        log.warning("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set — skipping migration check")
        return

    required_tables = ["enrichment_cache"]

    for table in required_tables:
        resp = httpx.get(
            f"{supabase_url}/rest/v1/{table}",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
            },
            params={"select": "id", "limit": "1"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            log.info("Table %s exists", table)
        elif resp.status_code == 404:
            log.warning(
                "Table %s NOT found — enrichment cache will be disabled. "
                "Apply migration 009_enrichment_cache.sql via Supabase SQL editor.",
                table,
            )
        else:
            log.warning("Table %s check returned status %d: %s", table, resp.status_code, resp.text[:200])