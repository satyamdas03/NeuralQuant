# Security Incident Response Runbook

NeuralQuant / nq-api. Owner: satyamdas03@gmail.com. Last updated: 2026-06-14 (roadmap P6).

This runbook is for **responding** to a suspected or confirmed security incident.
For the standing security posture and prior hardening, see
`SECURITY_IDOR_AUDIT.md`, `SECURITY_P0_P1_OPERATOR_ACTIONS.md`, and the
`session92_*` / `session93_*` memory notes.

---

## 0. Signals — how you find out

- **Audit log:** `public.security_events` (Supabase). Backed by
  `nq_api/auth/security_audit.py`. Query recent events:
  ```sql
  select event_type, severity, email, ip, detail, created_at
  from public.security_events
  where created_at > now() - interval '24 hours'
  order by created_at desc;
  ```
  Event types currently emitted: `admin_denied`, `rate_limit_block`,
  `stripe_webhook_unconfigured`, `stripe_webhook_bad_signature`.
- **Logs:** Render logs for `nq-api`. The redaction filter scrubs API keys,
  bearer tokens, and emails from plaintext — do not assume an email in a log
  line is the real value; use `security_events` for the unredacted trail.
- **CI:** `secret-scan.yml` (gitleaks) failing → a secret may have been
  committed. `dep-audit.yml` failing → a vulnerable dependency.
- **External:** Stripe/Supabase dashboards, GitHub security alerts, user reports.

## 1. Triage — classify severity

| Severity | Examples | Target response |
|----------|----------|-----------------|
| **SEV1 — critical** | live secret leaked & exploited, customer data exposed, unauthorized DB writes, payment fraud | immediate, drop everything |
| **SEV2 — high** | secret leaked but not yet exploited, auth bypass, repeated `stripe_webhook_bad_signature`, account takeover of one user | within hours |
| **SEV3 — medium** | sustained `rate_limit_block` from many IPs (abuse/DoS), single suspicious admin_denied burst | same day |
| **SEV4 — low** | dependency CVE with no known exploit, isolated anomaly | next business day |

Write down (in a scratch doc or the incident channel): what you saw, when,
which system, and your current severity guess. Re-classify as you learn more.

## 2. Contain

Pick the relevant playbook(s):

### A. Leaked credential / API key (FMP, Anthropic, Supabase, Stripe, LiveKit, Hermes)
1. **Rotate the key at the provider immediately.** Do not wait to confirm abuse.
2. Update the value in Render env (`nq-api` and any worker/agent service that
   uses it) → trigger a manual deploy.
3. If the leak was in git: rotate first, then purge — `gitleaks` already gates
   new commits, but history may need `git filter-repo` / BFG if the key is in a
   past commit. Rotation makes the leaked value useless regardless.
4. Check provider usage dashboards for anomalous spend/calls during the exposure
   window.

### B. Forged / replayed Stripe webhook (`stripe_webhook_bad_signature` or `_unconfigured`)
1. Confirm `STRIPE_WEBHOOK_SECRET` is set on `nq-api` (if `_unconfigured` fired,
   it is NOT — the request was refused with 503, which is correct, but set the
   secret now).
2. Audit `users` for tier changes you can't explain:
   ```sql
   select id, email, tier, subscription_status, updated_at
   from public.users where updated_at > now() - interval '7 days'
   order by updated_at desc;
   ```
3. Cross-check suspicious upgrades against real Stripe subscriptions in the
   Stripe dashboard. Revert any tier not backed by a real subscription.

### C. Account takeover / unauthorized access
1. Auth is Supabase-managed — revoke the user's sessions in the Supabase Auth
   dashboard; force a password reset.
2. Review `security_events` and `user_events` for that email/ip.
3. If an **admin** account is implicated: remove the email from `ADMIN_EMAILS`
   on `nq-api`, redeploy, then rotate that account's credentials before
   re-adding.

### D. Abuse / DoS (sustained `rate_limit_block`, or expensive endpoint hammered)
1. The in-process IP fuse (`auth/abuse_limit.py`) already 429s offenders
   (e.g. `livekit_token`, 20 / 5 min). Confirm it's firing in `security_events`.
2. If it's distributed beyond what the fuse handles, block at the edge
   (Cloudflare / Render) by IP or ASN.
3. For LiveKit/agent-cost abuse specifically: check LiveKit usage; tighten the
   fuse limit in `abuse_limit.py` if needed and redeploy.

### E. Data exposure (IDOR / over-broad query)
1. Identify the route and the data class. RLS (migration `020_enable_rls.sql`)
   is the backstop, but the backend uses `service_role`, which bypasses RLS — so
   the application-layer ownership filter is the real control.
2. Patch the route to filter by `user.id` / gate behind `require_admin`, deploy.
3. Estimate scope: which rows, whose, over what window. Note it for disclosure.

## 3. Eradicate & recover
- Deploy the fix (`nq-api` on Render usually needs a **manual** deploy — see
  memory notes; auto-deploy has been unreliable).
- Verify with `smoke_test.py` and a targeted check of the affected route.
- Confirm the signal has stopped in `security_events` / logs.
- Restore any data that was altered (DB backups: see
  `docs/EMERGENCY_SHUTDOWN_RESUME_PLAN.md`).

## 4. Post-incident
- Write a short timeline: detection → containment → fix → verification.
- Root cause + the one change that would have prevented it.
- File follow-ups (new test, new `security_events` event type, tighter limit).
- If customer data was exposed: determine disclosure obligations and notify.
- Update this runbook with anything that was missing.

## Quick reference — where things live
- Audit log table: `public.security_events` (migration `021_security_events.sql`)
- Audit emitter: `apps/api/src/nq_api/auth/security_audit.py`
- Admin gate: `require_admin` / `require_team_access` in `auth/deps.py` (`ADMIN_EMAILS`, `TEAM_API_TOKEN`)
- Abuse fuse: `auth/abuse_limit.py`
- Webhook verification: `routes/webhooks_stripe.py` (`STRIPE_WEBHOOK_SECRET`)
- Secret scanning: `.github/workflows/secret-scan.yml` (gitleaks)
- Dependency scanning: `.github/workflows/dep-audit.yml` + `.github/dependabot.yml`
- Log redaction: `nq_api/logging_redaction.py`
- RLS: `apps/api/migrations/020_enable_rls.sql`
