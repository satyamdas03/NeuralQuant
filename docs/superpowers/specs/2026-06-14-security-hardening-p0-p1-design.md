# Security Hardening — Audit + P0 (Secrets) + P1 (Authorization/RLS) — Design

Date: 2026-06-14 · Status: approved (brainstorm gate passed)

Goal: raise NeuralQuant to bank-grade, defense-in-depth security for a product storing user PII (emails, watchlists, conversations, sessions) and handling payments. This spec covers the **evidence-based audit** and the **P0 + P1** hardening for this session; P2–P6 are a roadmap for later sessions.

> Reality note: "literally unhackable" is not achievable; the goal is **defense in depth** — multiple independent layers so no single failure is catastrophic.

---

## 1. Audit findings (evidence-based)

### Strong baseline (already in place — do not regress)
- **JWT auth** verified properly: `auth/jwt_verify.py` uses JWKS (ES256/RS256) with HS256 fallback, checks signature, requires `exp`+`sub`+audience. Not decode-only.
- **CORS** scoped to known origins + regex (`config.py`), not `*`.
- **Webhook signatures verified**: Supabase auth webhook (HMAC-SHA256, `auth_webhook.py`), PayPal (`webhooks_paypal.py` → `verify_webhook_signature`).
- **Rate limiting** on the expensive endpoints: `enforce_tier_quota` / `enforce_guest_quota` on `analyst`, `query`, `screener`, `backtest`.
- **Secrets**: `.env` gitignored (only `.env.example` tracked); none committed.
- **Input/SSRF**: file MIME allow-lists (`upload_tools.py`); terminal/OpenBB proxy path-whitelisted to 67 endpoints (`terminal.py`).

### Confirmed gaps (this spec fixes P0 + P1; rest → roadmap)
| # | Severity | Finding | Phase |
|---|---|---|---|
| 1 | 🔴 | **FMP API key leaked** — appeared in prod logs and was pasted into chat. Key revoked. | P0 |
| 2 | 🔴 | **Secrets/PII in logs** — `httpx` INFO logs full request URLs incl. `?apikey=…`; user emails + ids logged at INFO. | P0 |
| 3 | 🔴 | **Service-role-everywhere → RLS off** — all DB access via `SUPABASE_SERVICE_ROLE_KEY` (33 uses / 23 files). Supabase RLS bypassed; cross-user safety depends 100% on app-layer `user_id` scoping → IDOR risk if any route slips. | P1 |
| 4 | 🟠 | **No RLS policies** on user-data tables — no DB-level safety net; direct-Supabase (anon-key) paths unprotected. | P1 |
| 5 | 🟠 | **No web security headers** — no CSP/HSTS/X-Frame-Options in `next.config`. | P4 |
| 6 | 🟠 | **File upload: no size cap** (MIME allow-list present, size unbounded → DoS). | P3 |
| 7 | 🟡 | **Smoke-secret** bypass mints a pro user if `SMOKE_TEST_SECRET` is set — needs strong-only activation + prod hygiene. | P0 |
| 8 | 🟡 | No automated **secret scanning** / dependency CVE scanning in CI. | P0/P5 |

---

## 2. P0 — Secrets & exposure (this session)

### 2.1 Rotate the leaked FMP key (USER action — documented, not code)
- In the FMP dashboard: revoke the leaked key, issue a new key.
- Update `FMP_API_KEY` on Render (`nq-api` + any worker that uses it) and local `.env`.
- Redeploy. Old key dies on revoke.
- Also review other keys that may have transited logs/chat (Anthropic, ElevenLabs, Supabase) — rotate any that did.

### 2.2 Log redaction (CODE)
- In `apps/api/src/nq_api/main.py` logging setup: raise the `httpx` logger to `WARNING` (kills the `apikey=` URL INFO spam).
- Add a `RedactingFilter` (`logging.Filter`) attached to the root logger that scrubs, in the final message string:
  - `apikey=<value>` → `apikey=***`
  - `Bearer <token>` / `apikey": "<token>"` → redacted
  - email addresses → `***@***`
  - long base64/hex secrets (`[A-Za-z0-9_-]{32,}`) following key-ish words
- Goal: no secret or raw email ever reaches stdout/Render logs.

### 2.3 Smoke-secret lockdown (CODE)
- In `auth/deps.py`, only honor the `X-Smoke-Secret` bypass when `SMOKE_TEST_SECRET` is set **and ≥ 24 chars** (reject weak/short secrets from accidentally enabling bypass). Document: leave `SMOKE_TEST_SECRET` **unset** on production `nq-api`; set only transiently when running smoke tests.

### 2.4 CI secret scanning (CODE)
- Add `.github/workflows/secret-scan.yml` running **gitleaks** on push + PR; fail the build on a finding. Add a `.gitleaks.toml` allowlisting `*.env.example` and known false positives.
- (Dependency CVE scanning — `pip-audit` / `npm audit` — deferred to P5.)

### 2.5 Client-bundle secret check (verification step)
- Grep the web build for any non-public secret: only `NEXT_PUBLIC_*` (Supabase anon key + public URLs) may ship to the client. Confirm no service-role key, Anthropic key, FMP key, etc. in `apps/web`.

---

## 3. P1 — Authorization / RLS (this session, the meat)

### 3.1 IDOR audit (CODE)
For every nq-api route that reads/writes a **user-owned** table, verify the query is scoped to the **authenticated** `user.id` from `get_current_user` — never to an id taken from the request that isn't re-checked.

User-owned tables + the files that touch them:
- `users` — `auth/deps.py`
- `watchlists` — `routes/watchlists.py`, `astra_portfolio.py`
- `alerts` — `routes/alerts.py`
- `conversations` — `routes/query.py` (and conversation history reads)
- `user_events` — `analytics.py`, `analytics_track.py`, `livekit_token.py`, `share.py`
- `user_profiles` — `auth.py`, `astra_portfolio.py`, `cron.py`
- `user_sessions`, `session_activities`, `session_reports` — `routes/session.py`, `session_analysis.py`
- `shared_analyses` — `routes/share.py`, `analytics.py` (**intentionally public-by-link** — see 3.3)
- `teams` / `team_members` — `routes/team.py`
- (Excluded: `signal_log` is global trading-daemon data, not user PII.)

Audit rule per route:
1. Mutations (`POST/PATCH/DELETE`) must set/match `user_id == user.id`.
2. Reads must filter `user_id = eq.{user.id}` (or join through an owned row).
3. Any `user_id` (or `session_id`, `id`) taken from request input must be **re-validated** to belong to `user.id` before use.
4. Fix violations; add a focused regression test for each fix where a pure function can assert scoping.

Output: a short `SECURITY_IDOR_AUDIT.md` table (route → table → verdict → fix) committed under `docs/`.

### 3.2 Enable RLS (defense-in-depth) — SQL migration (USER applies in Supabase)
New migration `apps/api/migrations/0XX_enable_rls.sql` (use the next free number ≥ 020):
- For each user-owned table: `alter table … enable row level security;` + a policy:
  ```sql
  create policy "owner_all" on public.<table>
    for all to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());
  ```
  (`users`: predicate `id = auth.uid()`.)
- **`service_role` bypasses RLS automatically** → the nq-api backend is unaffected. This is the key safety property: turning RLS on does not break the app; it only adds a net for direct-Supabase (anon/authenticated) access.
- Revoke broad `anon` access where present.
- Verification queries included in the migration comments (e.g., `select … as authenticated` returns only own rows).

### 3.3 `shared_analyses` — explicit public-by-link policy
The share feature is meant to be readable by anyone holding the link, but **not enumerable** and only **owner-writable**:
- `SELECT` policy: allow `anon` + `authenticated` to read a row **only when fetched by its unguessable share id/slug** (PostgREST filters by id; the slug is the capability). Do not grant blanket list/enumerate.
- `INSERT/UPDATE/DELETE`: `authenticated` and `user_id = auth.uid()` only.
- Confirm the share slug is high-entropy (UUID/random) — if not, note it as a follow-up.

### 3.4 Tests
- Unit: `RedactingFilter` redacts apikey/bearer/email; passes through clean text.
- Unit: smoke-secret bypass inactive when `SMOKE_TEST_SECRET` unset or < 24 chars; active when ≥ 24 + match.
- IDOR regression: for each fixed route, a test asserting the query is built with `user.id` (mock `_rest`/`_supabase_rest`, assert the `user_id=eq.<authed>` filter is present).

---

## 4. Roadmap (later sessions)
- **P2** abuse/auth resilience — confirm Stripe webhook sig (if used), rate-limit auth + voice/token endpoints, LiveKit token abuse, credential-stuffing protection.
- **P3** injection — prompt-injection guardrails on LLM endpoints, **file-upload size cap**, SSRF re-check on outbound proxies, path traversal.
- **P4** web/client — CSP, HSTS, X-Frame-Options, Permissions-Policy, cookie flags, SW integrity.
- **P5** supply chain — `pip-audit` + `npm audit` in CI, Dependabot, pin/lock review.
- **P6** monitoring/IR — audit log of security-relevant events, anomaly alerts, incident-response runbook.

## 5. Build order (this session)
1. P0.2 log redaction + P0.3 smoke lockdown (code + tests)
2. P0.4 CI secret scan
3. P0.5 client-bundle secret verification
4. P1.1 IDOR audit + fixes + `SECURITY_IDOR_AUDIT.md`
5. P1.2/3 RLS migration + share policy (SQL; user applies)
6. P0.1 key rotation — documented for the user (their action)

## Risks / notes
- Raising `httpx` to WARNING removes some debugging signal — acceptable; the redaction filter is the safety net if it's lowered again.
- RLS is additive (service_role bypasses), so zero backend-breakage risk — but **must be tested** that no frontend path relies on anon-key access to another user's rows.
- IDOR fixes must not break legitimate flows (e.g., `share` public read, `team` member access) — handle per-table, not blanket.
- Key rotation + RLS migration + Render env are deploy-time/user actions, tracked separately from code.
