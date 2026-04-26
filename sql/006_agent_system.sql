-- Agent system: logs, feedback, and scheduled tasks
-- All tables use service_role access only (no anon/public RLS needed)

-- Agent action logs: every action taken by every agent
CREATE TABLE IF NOT EXISTS agent_logs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_name  TEXT NOT NULL,                -- 'NQ-ENGINEER', 'NQ-GUARDIAN', etc.
    channel     TEXT NOT NULL,                -- Slack channel name (e.g., 'nq-engineer')
    action_type TEXT NOT NULL,                -- 'analysis', 'deploy', 'alert', 'response', etc.
    input_text  TEXT,                          -- What the human said (truncated to 2000 chars)
    output_text TEXT,                          -- What the agent responded (truncated to 4000 chars)
    metadata   JSONB DEFAULT '{}',            -- Structured data (model, tokens, scores, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for recent queries per agent
CREATE INDEX idx_agent_logs_agent_time ON agent_logs (agent_name, created_at DESC);
CREATE INDEX idx_agent_logs_channel ON agent_logs (channel, created_at DESC);

-- Human approval / rejection of agent actions
CREATE TABLE IF NOT EXISTS agent_feedback (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    log_id      BIGINT REFERENCES agent_logs(id),
    feedback_type TEXT NOT NULL,               -- 'approved', 'rejected', 'modified', 'commented'
    feedback_text TEXT,                         -- Human's feedback comment
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_feedback_log ON agent_feedback (log_id);

-- Scheduled tasks for agent automation
CREATE TABLE IF NOT EXISTS agent_schedules (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    task_type   TEXT NOT NULL,                 -- 'daily_wrap', 'market_scan', 'security_audit', etc.
    cron_expr   TEXT,                           -- e.g., '0 9 * * 1-5' (9am weekdays)
    last_run_at TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- RLS: service_role can do everything, anon has no access
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_schedules ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on agent_logs"
    ON agent_logs FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on agent_feedback"
    ON agent_feedback FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on agent_schedules"
    ON agent_schedules FOR ALL
    USING (auth.role() = 'service_role');