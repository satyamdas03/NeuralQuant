-- 021_security_events.sql — audit trail for security-relevant events (roadmap P6).
--
-- Written by the backend via service_role (see auth/security_audit.py). RLS is
-- enabled with NO policies, so only service_role (which bypasses RLS) can read
-- or write — anon/authenticated clients see nothing. Mirrors the lock-down
-- approach in 020_enable_rls.sql.
--
-- Apply in the Supabase SQL editor.

create table if not exists public.security_events (
    id          uuid primary key default gen_random_uuid(),
    event_type  text not null,
    severity    text not null default 'warning',
    email       text,
    ip          text,
    detail      text,
    created_at  timestamptz not null default now()
);

create index if not exists security_events_created_idx on public.security_events (created_at desc);
create index if not exists security_events_type_idx    on public.security_events (event_type);

alter table public.security_events enable row level security;
-- Intentionally no policies: service_role only.

-- Verification:
--   select count(*) from public.security_events;
--   select event_type, severity, count(*) from public.security_events
--     where created_at > now() - interval '24 hours' group by 1, 2 order by 3 desc;
