-- 020_enable_rls.sql — defense-in-depth Row Level Security.
--
-- The nq-api backend connects with the Supabase service_role key, which BYPASSES
-- RLS — so applying this migration does NOT change backend behavior. It only adds
-- a database-level safety net for any direct-Supabase (anon / authenticated key)
-- access, so a user can never read or write another user's rows even if an
-- app-layer filter is ever missed.
--
-- Idempotent + tolerant: every table is guarded with to_regclass(), so tables that
-- don't exist in this project are simply skipped (no error). Safe to re-run.
-- Apply in the Supabase SQL editor.

-- ---- tables owned directly via a user_id column ----
do $$
declare t text;
begin
  foreach t in array array[
    'watchlists','alerts','alert_subscriptions','alert_deliveries','conversations',
    'user_events','user_profiles','user_sessions','session_reports',
    'session_activities'
  ]
  loop
    if to_regclass('public.'||t) is not null then
      execute format('alter table public.%I enable row level security;', t);
      execute format('drop policy if exists owner_all on public.%I;', t);
      execute format(
        'create policy owner_all on public.%I for all to authenticated '
        'using (user_id = auth.uid()) with check (user_id = auth.uid());', t);
    end if;
  end loop;
end $$;

-- ---- users: owned via id ----
do $$
begin
  if to_regclass('public.users') is not null then
    alter table public.users enable row level security;
    drop policy if exists owner_self on public.users;
    create policy owner_self on public.users for all to authenticated
      using (id = auth.uid()) with check (id = auth.uid());
  end if;
end $$;

-- ---- shared_analyses: PUBLIC read-by-link, owner-only write (creator_id) ----
-- share_id is a high-entropy capability (secrets.token_urlsafe(12)); callers fetch
-- by share_id, so public SELECT does not enable useful enumeration.
do $$
begin
  if to_regclass('public.shared_analyses') is not null then
    alter table public.shared_analyses enable row level security;
    drop policy if exists public_read on public.shared_analyses;
    drop policy if exists owner_write on public.shared_analyses;
    create policy public_read on public.shared_analyses
      for select to anon, authenticated using (true);
    create policy owner_write on public.shared_analyses
      for all to authenticated
      using (creator_id = auth.uid()) with check (creator_id = auth.uid());
  end if;
end $$;

-- ---- team_members: members only ----
do $$
begin
  if to_regclass('public.team_members') is not null then
    alter table public.team_members enable row level security;
    drop policy if exists member_access on public.team_members;
    create policy member_access on public.team_members for all to authenticated
      using (user_id = auth.uid()) with check (user_id = auth.uid());
  end if;
end $$;

-- ---- teams: visible to members ----
do $$
begin
  if to_regclass('public.teams') is not null
     and to_regclass('public.team_members') is not null then
    alter table public.teams enable row level security;
    drop policy if exists team_member_access on public.teams;
    create policy team_member_access on public.teams for select to authenticated
      using (id in (select team_id from public.team_members where user_id = auth.uid()));
  end if;
end $$;

-- ---- VERIFICATION (run as a sample authenticated user; expect only own rows) ----
-- select set_config('request.jwt.claim.sub', '<A-REAL-USER-UUID>', true);
-- set local role authenticated;
-- select count(*) from public.watchlists;        -- should = that user's row count only
-- select count(*) from public.user_profiles;     -- same
-- reset role;
--
-- To see which tables actually got RLS enabled afterwards:
-- select relname from pg_class where relrowsecurity and relnamespace = 'public'::regnamespace order by relname;
