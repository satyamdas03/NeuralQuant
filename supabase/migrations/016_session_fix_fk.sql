-- Fix: remove FK on user_id — guests don't have auth.users rows
-- Backend uses service_role key, bypasses RLS. Run this in Supabase SQL Editor.

ALTER TABLE public.user_sessions DROP CONSTRAINT IF EXISTS user_sessions_user_id_fkey;
ALTER TABLE public.session_activities DROP CONSTRAINT IF EXISTS session_activities_user_id_fkey;
ALTER TABLE public.session_reports DROP CONSTRAINT IF EXISTS session_reports_user_id_fkey;
