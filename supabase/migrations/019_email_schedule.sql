-- 019_email_schedule.sql
-- Track onboarding email sends to avoid duplicates

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS welcome_email_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS debate_demo_email_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS screener_email_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS upgrade_email_sent_at TIMESTAMPTZ;

COMMENT ON COLUMN public.users.welcome_email_sent_at IS 'Timestamp when Day-0 welcome email was sent';
COMMENT ON COLUMN public.users.debate_demo_email_sent_at IS 'Timestamp when Day-1 PARA-DEBATE demo email was sent';
COMMENT ON COLUMN public.users.screener_email_sent_at IS 'Timestamp when Day-3 screener intro email was sent';
COMMENT ON COLUMN public.users.upgrade_email_sent_at IS 'Timestamp when Day-7 upgrade prompt email was sent';