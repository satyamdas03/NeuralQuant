# NeuralQuant — Handover Runbook

Asset-transfer procedure for an acquisition close. Operational shutdown/resume
detail (scale-to-zero, cost table, resume steps) lives in
[EMERGENCY_SHUTDOWN_RESUME_PLAN.md](EMERGENCY_SHUTDOWN_RESUME_PLAN.md) — this
file covers what changes hands and in what order.

## Transfer order (do not reorder)

1. **Escrow funded / payment confirmed** — nothing transfers before this.
2. GitHub repo transfer
3. Supabase project transfer
4. Domain transfer (neuralquant.co)
5. Render + Vercel project transfer (or buyer redeploys fresh)
6. Key rotation (ALL keys — see checklist)
7. Data exports handed over
8. Founder transition period begins (if contracted)

## 1. GitHub repositories

- `NeuralQuant` (this repo) + sister repo `anjali-value-stocks`.
- Settings → Transfer ownership → buyer's org. Repo must remain **private**.
- During diligence (pre-close): grant read access to named GitHub accounts
  under NDA only. Never flip to public.

## 2. Supabase

- Org Settings → Transfer project to buyer's organization (buyer needs a
  Supabase account; transfer preserves data, URL, and keys).
- Alternative: fresh project + `supabase/migrations/001–025` +
  `scripts/backup_database.py` restore.
- Tables with user PII (auth.users, user_profiles, session tracking): purge or
  contractually scope before transfer per the APA.

## 3. Domain (neuralquant.co)

- Registrar: Porkbun. Unlock → auth/EPP code → buyer initiates transfer at
  their registrar (5–7 days) — or push within Porkbun (instant, buyer needs
  Porkbun account).
- DNS to recreate: Vercel A/CNAME for web, Resend TXT/DKIM for email.

## 4. Render / Vercel

- Render: Team transfer, or buyer creates own services from `render.yaml`
  (blueprint is the source of truth) and sets env vars from `.env.example`.
- Vercel: project transfer to buyer team; rootDirectory must stay `apps/web`.
- Either way buyer re-subscribes FMP Premium ($49/mo) — subscriptions are
  non-transferable.

## 5. Key rotation checklist (ALL rotate at close)

| Key | Where used | Rotate at |
|---|---|---|
| ANTHROPIC_API_KEY | agents, query, Morgan | console.anthropic.com |
| AWS access keys (Bedrock) | LLM alt path | IAM |
| SUPABASE_SERVICE_ROLE_KEY + JWT secret | API ↔ DB | Supabase dashboard |
| FMP_API_KEY | market data | buyer's own subscription |
| FINNHUB / FRED / TWELVE_DATA | data | free re-register |
| RESEND_API_KEY | email | resend.com |
| LIVEKIT / DEEPGRAM / ELEVENLABS | voice | respective consoles |
| STRIPE / PAYPAL secrets + webhook IDs | payments | buyer's own accounts |
| CRON_SECRET / SMOKE_TEST_SECRET | internal auth | generate new |

`apps/api/.env` on the founder's machine contains live secrets — it is NOT in
the repo and is destroyed after rotation, per APA.

## 6. Data exports included

- Full Supabase dump (pg_dump, no PII unless contracted).
- Q1FY27 quarterly backtest: `quarterly_test_runs` / `quarterly_test_results`
  CSVs (also bundled in `data/demo_snapshot/`).
- Demo snapshot (5 tables, 1,669 rows) already in-repo.

## 7. Founder transition (optional, recommended)

3–6 months part-time: architecture walkthroughs, Anjali pipeline handover,
on-call for production incidents, integration support with buyer's stack.
The 82 session memory documents + docs/ bundle are the written backstop.
