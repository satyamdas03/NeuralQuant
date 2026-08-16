-- Migration 028: Remove email-related schema after email functionality was disabled.
-- Apply after 027_security_events.sql and 022_score_cache_growth_percentile.sql.

-- 1. Opt-in flag for daily market wrap emails (feature removed).
ALTER TABLE public.user_profiles
    DROP COLUMN IF EXISTS email_market_wrap;

-- 2. Session report email tracking (reports are now stored only; not emailed).
ALTER TABLE public.session_reports
    DROP COLUMN IF EXISTS email_sent,
    DROP COLUMN IF EXISTS email_sent_at;

-- 3. Alert subscriptions + deliveries were only used for email alerts.
DROP TABLE IF EXISTS public.alert_deliveries;
DROP TABLE IF EXISTS public.alert_subscriptions;
