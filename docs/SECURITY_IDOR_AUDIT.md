# IDOR Audit — user-data routes (2026-06-14)

Audit of every nq-api route touching user-owned tables. Rule: every read/write must
scope to the **authenticated `user.id`** from `get_current_user`, never to an
unchecked client-supplied id. Backend uses `service_role` (RLS bypassed), so this
app-layer scoping is the primary protection (RLS added in `020_enable_rls.sql` as a net).

| Route (method path) | Table(s) | Owner column | Scoped to user.id? | Verdict | Action |
|---|---|---|---|---|---|
| GET /watchlist | watchlists | user_id | `user_id=eq.user.id` | PASS | none |
| POST /watchlist | watchlists | user_id | insert `user_id=user.id` | PASS | none |
| DELETE /watchlist/{id} | watchlists | user_id | `id` AND `user_id=eq.user.id` | PASS | none |
| GET /alerts/subscriptions | alert_subscriptions | user_id | `user_id=eq.user.id` | PASS | none |
| POST /alerts/subscriptions | alert_subscriptions | user_id | insert `user_id=user.id` | PASS | none |
| DELETE /alerts/subscriptions/{id} | alert_subscriptions | user_id | `id` AND `user_id=eq.user.id` | PASS | none |
| GET /alerts/deliveries | alert_deliveries | user_id | `user_id=eq.user.id` | PASS | none |
| POST /session/start, /activity | user_sessions, session_activities | user_id | writes `user_id` (or guest id) | PASS | none |
| POST /session/end | user_sessions | user_id | re-validates `stored_user_id == user.id` | PASS | none |
| GET /session/reports | session_reports | user_id | `user_id=eq.user.id` | PASS | none |
| GET /session/report/{id} | session_reports | user_id | `id` AND `user_id=eq.user.id` | PASS | none |
| POST /share/analysis | shared_analyses | creator_id | sets `creator_id=user.id` | PASS | none |
| GET /share/analysis/{share_id} | shared_analyses | creator_id | public-by-capability (`share_id` = `secrets.token_urlsafe(12)`, ~96-bit) + `is_public=true` | PASS | intentional public read; slug high-entropy |
| DELETE /share/analysis/{share_id} | shared_analyses | creator_id | re-checks `creator_id == user.id` → 403 | PASS | none |
| GET/POST/PATCH /astra/* (profiles) | user_profiles, watchlists | user_id | `user_id=eq.user.id` | PASS | none |
| GET /auth/me/profile | user_profiles | user_id | scoped to authed user | PASS | none |
| POST /analytics/track | user_events | user_id | writes authed user_id (fixed prior session) | PASS | none |
| GET /internal/analytics/dashboard | user_events, shared_analyses (aggregate) | — | **was gated on tier (pro/api)** | **FIXED** | now gated on `ADMIN_EMAILS` allowlist (a paying customer is not an admin) |
| GET/POST/PATCH /team/tasks, /standups | teams, team_members, tasks, standups | team-shared | auth required; team-collaboration data | REVIEW | verify team_id membership scoping — tracked as **P2 follow-up** |
| cron jobs (user_profiles etc.) | user_profiles | — | server-side trusted job, gated by cron secret (no per-user request) | PASS | acceptable; not user-facing |

## Findings
- **1 real issue fixed:** `/internal/analytics/dashboard` exposed platform-wide growth metrics + user ids to any **pro/api-tier** user (tier ≠ admin). Now gated on an `ADMIN_EMAILS` allowlist. Operator must set `ADMIN_EMAILS` on nq-api.
- **1 follow-up (P2):** `team.py` tasks/standups are team-shared collaboration data behind auth — confirm each query scopes to the caller's team membership (not blanket). Low risk (internal team feature, no PII like conversations), deferred.
- Everything else: **PASS** — the codebase consistently scopes user-data reads/writes to `user.id`, and IDOR-prone by-id deletes/reads re-validate ownership.

## Defense-in-depth
RLS migration `apps/api/migrations/020_enable_rls.sql` adds DB-level per-user policies as a net beneath this app-layer scoping. `shared_analyses` owner policy uses `creator_id` (confirmed here).
