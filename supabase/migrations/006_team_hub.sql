-- Team Hub: task tracking + agent standups for closed-loop operations
-- Agents and human orchestrator coordinate through these tables.

-- Agent roles that can be assigned tasks
CREATE TYPE agent_role AS ENUM (
    'NQ-Engineer',
    'NQ-Guardian',
    'NQ-Content',
    'NQ-Analyst-Ops',
    'NQ-Quant',
    'NQ-Biz',
    'NQ-Intel',
    'NQ-Support',
    'Satyam'
);

-- Task statuses in the closed-loop pipeline
-- pending → in_progress → in_review → done
--                            ↓
--                         blocked (needs human input)
CREATE TYPE task_status AS ENUM (
    'pending',
    'in_progress',
    'in_review',
    'done',
    'blocked'
);

-- Priority levels
CREATE TYPE task_priority AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

-- ─── team_tasks ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS team_tasks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT NOT NULL,
    description   TEXT,
    -- Who is responsible for this task
    assignee      agent_role NOT NULL,
    -- Who created the task (may differ from assignee)
    created_by    agent_role NOT NULL DEFAULT 'Satyam',
    status        task_status NOT NULL DEFAULT 'pending',
    priority      task_priority NOT NULL DEFAULT 'medium',
    -- What type of work this is
    category      TEXT NOT NULL DEFAULT 'general',
    -- Agent output / deliverable (code, analysis, content, etc.)
    output        TEXT,
    -- Human review notes (only Satyam writes these)
    review_notes  TEXT,
    -- Related resource (PR URL, doc path, etc.)
    reference_url TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── team_standups ─────────────────────────────────────────────────────────────
-- Daily or per-session summaries from each agent
CREATE TABLE IF NOT EXISTS team_standups (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_role    agent_role NOT NULL,
    -- What was accomplished
    summary       TEXT NOT NULL,
    -- What's blocking progress
    blockers      TEXT,
    -- What's planned next
    next_actions  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Indexes ────────────────────────────────────────────────────────────────────
CREATE INDEX idx_tasks_assignee ON team_tasks(assignee);
CREATE INDEX idx_tasks_status ON team_tasks(status);
CREATE INDEX idx_tasks_priority ON team_tasks(priority);
CREATE INDEX idx_tasks_created_at ON team_tasks(created_at DESC);
CREATE INDEX idx_standups_agent ON team_standups(agent_role);
CREATE INDEX idx_standups_created ON team_standups(created_at DESC);

-- ─── Auto-update updated_at ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_team_tasks_updated
    BEFORE UPDATE ON team_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ─── RLS ────────────────────────────────────────────────────────────────────────
-- Team hub is internal — only authenticated users can access
ALTER TABLE team_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_standups ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view team tasks" ON team_tasks
    FOR SELECT USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can manage team tasks" ON team_tasks
    FOR ALL USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can view standups" ON team_standups
    FOR SELECT USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can manage standups" ON team_standups
    FOR ALL USING (auth.uid() IS NOT NULL);