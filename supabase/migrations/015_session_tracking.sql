-- Session tracking: log every user action, generate post-session MoM reports
-- Run: psql <connection> -f supabase/migrations/015_session_tracking.sql

CREATE TABLE IF NOT EXISTS public.user_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    duration_seconds INT,
    user_agent      TEXT,
    ip_address      TEXT,
    is_guest        BOOLEAN DEFAULT false,
    metadata        JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON public.user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_started_at ON public.user_sessions(started_at DESC);

CREATE TABLE IF NOT EXISTS public.session_activities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES public.user_sessions(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL,
    activity_type   TEXT NOT NULL,
    category        TEXT NOT NULL,
    label           TEXT,
    payload         JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_activities_session_id ON public.session_activities(session_id);
CREATE INDEX IF NOT EXISTS idx_session_activities_user_id ON public.session_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_session_activities_created_at ON public.session_activities(created_at);

CREATE TABLE IF NOT EXISTS public.session_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES public.user_sessions(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL,
    report_text     TEXT,
    summary         TEXT,
    email_sent      BOOLEAN DEFAULT false,
    email_sent_at   TIMESTAMPTZ,
    generated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_reports_user_id ON public.session_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_session_reports_session_id ON public.session_reports(session_id);

-- RLS: users can read their own sessions, activities, and reports
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.session_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.session_reports ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if re-running
DO $$ BEGIN
    EXECUTE 'DROP POLICY IF EXISTS "Users can view own sessions" ON public.user_sessions';
    EXECUTE 'DROP POLICY IF EXISTS "Users can view own activities" ON public.session_activities';
    EXECUTE 'DROP POLICY IF EXISTS "Users can view own reports" ON public.session_reports';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE POLICY "Users can view own sessions" ON public.user_sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view own activities" ON public.session_activities
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view own reports" ON public.session_reports
    FOR SELECT USING (auth.uid() = user_id);
