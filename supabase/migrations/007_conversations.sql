-- 007_conversations.sql
-- Persistent conversation memory for Ask AI (Step 10 of quality spec)

CREATE TABLE IF NOT EXISTS public.conversations (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    session_key  text NOT NULL,       -- client-generated key to group turns
    role         text NOT NULL CHECK (role IN ('user', 'assistant')),
    content      text NOT NULL,
    ticker       text,
    market       text DEFAULT 'US',
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Index for fast session lookup
CREATE INDEX IF NOT EXISTS idx_conversations_session
    ON public.conversations (user_id, session_key, created_at DESC);

-- RLS: users can only read/write their own conversations
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversations_user_rw ON public.conversations
    FOR ALL USING (auth.uid() = user_id);

-- Auto-cleanup: delete conversations older than 90 days
-- (pg_cron or manual cleanup)