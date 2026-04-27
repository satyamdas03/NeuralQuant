"""One-time migration endpoint for team_hub tables.

Creates ENUM types, tables, indexes, triggers, and RLS policies.
Safe to run multiple times — uses IF NOT EXISTS / CREATE OR REPLACE.
Remove this file after migration is confirmed.

GET /migrate/team-hub — runs the migration, returns status.
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/migrate", tags=["migrate"])
log = logging.getLogger(__name__)


def _run_sql(sql: str) -> dict:
    """Execute DDL SQL via direct PostgreSQL connection."""
    db_url = os.environ.get("SUPABASE_DB_URL", "")

    if not db_url:
        raise HTTPException(status_code=503, detail="SUPABASE_DB_URL not configured")

    try:
        import psycopg2

        conn = psycopg2.connect(db_url, sslmode="require", connect_timeout=15)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        rowcount = cur.rowcount if hasattr(cur, "rowcount") else -1
        result = cur.fetchall() if cur.description else []
        cur.close()
        conn.close()
        return {"method": "psycopg2", "rows_affected": rowcount, "result": result}
    except Exception as exc:
        log.exception("psycopg2 migration failed")
        raise HTTPException(status_code=500, detail=f"Migration failed: {exc}")


MIGRATION_SQL = """
-- ENUM types (idempotent via DO blocks)
DO $$ BEGIN
    CREATE TYPE agent_role AS ENUM (
        'NQ-Engineer', 'NQ-Guardian', 'NQ-Content', 'NQ-Analyst-Ops',
        'NQ-Quant', 'NQ-Biz', 'NQ-Intel', 'NQ-Support', 'Satyam'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE task_status AS ENUM ('pending', 'in_progress', 'in_review', 'done', 'blocked');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE task_priority AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Tables
CREATE TABLE IF NOT EXISTS team_tasks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT NOT NULL,
    description   TEXT,
    assignee      agent_role NOT NULL,
    created_by    agent_role NOT NULL DEFAULT 'Satyam',
    status        task_status NOT NULL DEFAULT 'pending',
    priority      task_priority NOT NULL DEFAULT 'medium',
    category      TEXT NOT NULL DEFAULT 'general',
    output        TEXT,
    review_notes  TEXT,
    reference_url TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS team_standups (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_role    agent_role NOT NULL,
    summary       TEXT NOT NULL,
    blockers      TEXT,
    next_actions  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON team_tasks(assignee);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON team_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON team_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON team_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_standups_agent ON team_standups(agent_role);
CREATE INDEX IF NOT EXISTS idx_standups_created ON team_standups(created_at DESC);

-- Trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_team_tasks_updated ON team_tasks;
CREATE TRIGGER trg_team_tasks_updated
    BEFORE UPDATE ON team_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- RLS
ALTER TABLE team_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_standups ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can view team tasks" ON team_tasks;
DROP POLICY IF EXISTS "Authenticated users can manage team tasks" ON team_tasks;
DROP POLICY IF EXISTS "Authenticated users can view standups" ON team_standups;
DROP POLICY IF EXISTS "Authenticated users can manage standups" ON team_standups;

CREATE POLICY "Authenticated users can view team tasks" ON team_tasks
    FOR SELECT USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can manage team tasks" ON team_tasks
    FOR ALL USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can view standups" ON team_standups
    FOR SELECT USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can manage standups" ON team_standups
    FOR ALL USING (auth.uid() IS NOT NULL);
"""


@router.get("/team-hub")
def migrate_team_hub() -> dict:
    """Run the team_hub migration. Safe to call multiple times."""
    try:
        result = _run_sql(MIGRATION_SQL)
        return {"status": "ok", "detail": "Migration applied successfully", **result}
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Migration failed")
        raise HTTPException(status_code=500, detail=f"Migration failed: {exc}")


@router.get("/test-db")
def test_db_connection() -> dict:
    """Test database connectivity for debugging."""
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    if not db_url:
        return {"status": "error", "detail": "SUPABASE_DB_URL not set"}

    # Mask password
    masked = db_url.split("@")[0].rsplit(":", 1)[0] + ":***@" + db_url.split("@")[1] if "@" in db_url else db_url

    try:
        import psycopg2
        conn = psycopg2.connect(db_url, sslmode="require", connect_timeout=15)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        # Check if tables exist
        cur.execute("SELECT tablename FROM pg_tables WHERE tablename IN ('team_tasks', 'team_standups')")
        tables = [r[0] for r in cur.fetchall()]
        # Check if enums exist
        cur.execute("SELECT typname FROM pg_type WHERE typname IN ('agent_role', 'task_status', 'task_priority')")
        enums = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"status": "ok", "postgres_version": version, "tables_found": tables, "enums_found": enums}
    except Exception as exc:
        return {"status": "error", "detail": str(exc), "db_url_masked": masked}