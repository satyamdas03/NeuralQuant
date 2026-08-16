-- Migration 029: Drop leftover email columns on public.users.
-- 028 removed the email feature but only dropped user_profiles.email_market_wrap,
-- session_reports.email_*, and the alert_* tables. These four columns on
-- public.users were added by 019_email_schedule and are now unused (no code
-- references them). Optional cleanup — safe to skip.
ALTER TABLE public.users
    DROP COLUMN IF EXISTS welcome_email_sent_at,
    DROP COLUMN IF EXISTS debate_demo_email_sent_at,
    DROP COLUMN IF EXISTS screener_email_sent_at,
    DROP COLUMN IF EXISTS upgrade_email_sent_at;
