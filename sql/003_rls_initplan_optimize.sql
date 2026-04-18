-- RLS perf fix: wrap auth.uid() in subselect so Postgres evaluates it once,
-- not per-row. (advisor fix: auth_rls_initplan)
DROP POLICY IF EXISTS users_select_own ON public.users;
CREATE POLICY users_select_own ON public.users
  FOR SELECT USING ((SELECT auth.uid()) = id);

DROP POLICY IF EXISTS users_update_own ON public.users;
CREATE POLICY users_update_own ON public.users
  FOR UPDATE USING ((SELECT auth.uid()) = id);

DROP POLICY IF EXISTS watchlists_all_own ON public.watchlists;
CREATE POLICY watchlists_all_own ON public.watchlists
  FOR ALL USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS usage_select_own ON public.usage_log;
CREATE POLICY usage_select_own ON public.usage_log
  FOR SELECT USING ((SELECT auth.uid()) = user_id);
