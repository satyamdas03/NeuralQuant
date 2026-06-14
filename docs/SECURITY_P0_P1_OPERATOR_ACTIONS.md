# Security P0/P1 — Operator Actions (do these by hand)

These are the non-code steps the code changes depend on. Do them after the
`session92-security-p0-p1` branch is merged + deployed.

## 1. Rotate the leaked FMP key (URGENT)
The key `pBgk4hR1ikd8c1llnvNhR7gKjafv8Fn2` was exposed in logs/chat — it is burned.
1. FMP dashboard → API keys → **revoke** the old key, **generate** a new one.
2. Update `FMP_API_KEY` on Render (`nq-api` + any worker that uses it) and in local `.env`.
3. Redeploy `nq-api`. Verify a stock query returns prices.
4. Review whether any OTHER key (Anthropic, ElevenLabs, Deepgram, Supabase) transited
   logs/chat; rotate any that did.

## 2. Set ADMIN_EMAILS (required for the analytics dashboard fix)
The `/internal/analytics/dashboard` was gated on subscription tier (any pro/api user
could see platform-wide metrics). It is now gated on an explicit allowlist.
- On Render `nq-api`, set `ADMIN_EMAILS=satyamdas03@gmail.com` (comma-separate for more).
- If unset, the dashboard returns 403 for everyone (safe default).

## 3. Apply the RLS migration
1. Supabase Dashboard → SQL Editor → paste `apps/api/migrations/020_enable_rls.sql` → Run.
2. Run the verification block at the bottom as a sample user; confirm only that user's
   rows return.
3. Smoke-test the app end-to-end. The backend uses `service_role` (bypasses RLS), so
   nothing should break — this confirms no frontend path relied on cross-user anon access.
4. If a table doesn't exist or uses a different owning column, adjust that line and re-run.

## 4. Smoke secret hygiene
- Ensure `SMOKE_TEST_SECRET` is **unset** on production `nq-api`. Set it (>= 24 random
  chars) only transiently when running smoke tests, then unset. (Code now ignores any
  secret shorter than 24 chars, so a weak value can't enable the bypass.)

## 5. Confirm CI secret scan is green
- After pushing, check the `secret-scan` GitHub Action passes. If it flags a historical
  secret, rotate that secret first, then add a narrowly-scoped allowlist entry in
  `.gitleaks.toml`.

## What changed in code (this branch)
- Log redaction filter (apikey/bearer/email scrubbed; httpx URL logging silenced).
- Smoke bypass requires a strong (>= 24 char) `SMOKE_TEST_SECRET`.
- gitleaks CI workflow + config.
- Analytics admin gate: tier → `ADMIN_EMAILS` allowlist.
- IDOR audit (`docs/SECURITY_IDOR_AUDIT.md`) — all user-data routes PASS except the
  analytics gate (fixed) and a P2 follow-up on `team.py`.
- RLS migration `020_enable_rls.sql` (apply per step 3).

## Deferred to later sessions (roadmap)
P2 abuse/webhooks · P3 injection + upload size cap · P4 web headers (CSP/HSTS) ·
P5 pip/npm audit + Dependabot · P6 audit log + anomaly alerts + IR runbook ·
P2 follow-up: verify `team.py` task/standup queries scope to the caller's team.
