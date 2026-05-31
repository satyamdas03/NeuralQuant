-- 018_user_events.sql
-- Analytics event tracking for YC growth metrics (WAU, viral coefficient, etc.)

CREATE TABLE IF NOT EXISTS public.user_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id),        -- NULL for anonymous
    session_id  TEXT,                                   -- guest session ID from client
    event_type  TEXT NOT NULL,                          -- analysis_run, analysis_shared, analysis_viewed, signup_from_share, etc.
    category    TEXT NOT NULL DEFAULT 'engagement',     -- engagement, auth, share, revenue
    label       TEXT,                                   -- human-readable label (e.g. "PARA-DEBATE: AAPL")
    payload     JSONB DEFAULT '{}'::jsonb,              -- arbitrary event data
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_events_event_type ON public.user_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_events_created_at ON public.user_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_events_user_id ON public.user_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_events_category ON public.user_events(category);

ALTER TABLE public.user_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access user events" ON public.user_events
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Users read own events" ON public.user_events
    FOR SELECT USING (auth.uid() = user_id);

COMMENT ON TABLE public.user_events IS 'Analytics events for growth metrics: WAU, viral coefficient, feature usage.';