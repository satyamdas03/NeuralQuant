# NeuralQuant — Operations

What it costs to run, what runs where, and how to deploy.

## Environment variables

Complete annotated template: [.env.example](../.env.example) at repo root.
Minimum live set: `ANTHROPIC_API_KEY` (or AWS Bedrock creds + `USE_BEDROCK=true`),
`FMP_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`.
Demo set: none (`DEMO_MODE=true`).

## External services + monthly cost

| Service | Role | Monthly |
|---|---|---|
| FMP Premium | primary US market data (750 calls/min) | $49 |
| Render | 4 services + 4 cron jobs (see below) | ~$100–150 |
| Supabase | Postgres + auth + PostgREST | $0 (free) – $25 (pro) |
| Vercel | Next.js frontend hosting | $0 (hobby) |
| Anthropic / Bedrock | LLM (PARA-DEBATE, Ask AI, Morgan) | usage-based |
| LiveKit + Deepgram + ElevenLabs | voice agent (optional) | usage-based |
| Resend | transactional email | $0 (free tier) |
| Porkbun | neuralquant.co domain | ~$1 |

Fixed run-rate ≈ **$51/week** all-in (detail: EMERGENCY_SHUTDOWN_RESUME_PLAN.md).

## Render services (render.yaml)

| Service | Type | Plan | Purpose |
|---|---|---|---|
| nq-api | web | Pro | FastAPI backend |
| nq-openbb | web | Standard | OpenBB Platform proxy (Terminal) |
| nq-trader | worker | Starter | trading daemon (paper) |
| quantastra-agent | worker | Standard | LiveKit voice agent |
| nq-anjali-refresh | cron `0 2 * * *` | Starter | Anjali Excel → quantfactor sync |
| nq-market-refresh | cron `30 20 * * 1-5` | Starter | stock_meta + price refresh |
| nq-wrap-in | cron `0 11 * * 1-5` | Starter | India EOD market wrap email |
| nq-wrap-us | cron `30 21 * * 1-5` | Starter | US EOD market wrap email |

Cron services call `POST /cron/*` on nq-api with the `X-Cron-Secret` HTTP
header (`CRON_SECRET` env var). The cron bodies are thin wrappers in
`scripts/cron_invoke.py`; each service in `render.yaml` passes `CRON_SECRET` as
a synced (`sync: false`) secret. To add a new job, create another `type: cron`
entry in `render.yaml`, point `startCommand` at `python scripts/cron_invoke.py
<endpoint>`, and ensure `CRON_SECRET` is available.

## Hermes live trading agent

The `/hermes` page proxies the Hermes trading-agent state API running on Railway.
Only `nq-api` talks directly to Railway; the browser never sees the upstream URL
or secret.

Required env vars on `nq-api`:

| Var | Purpose |
|---|---|
| `HERMES_API_URL` | Base URL of the Hermes Railway service |
| `HERMES_API_SECRET` | Shared secret forwarded as `X-Hermes-Secret` |

Optional Hermes-daemon vars (set on the Railway service itself, see
`hermes-trading/README.md`):

| Var | Purpose |
|---|---|
| `HERMES_TRADING_MODE` | `paper` (default) or `live` |
| `HERMES_API_PORT` | Port for the daemon's state API |
| `HERMES_BIN` / `HERMES_MODEL` | Reflection CLI + model overrides |
| `RESEED_STRATEGY` | One-time reset flag; set once, then remove |

## Deploy

**Render (current):** push to `master` → *manual* deploy from Render Dashboard
(auto-deploy webhook is unreliable — known issue). Verify:
`curl https://neuralquant.onrender.com/health` → check `version` and
`score_cache_age_hours`.

**Vercel:** GitHub App auto-deploys `apps/web` on push (rootDirectory must stay
`apps/web` — was the cause of a multi-session deploy outage).

**AWS Bedrock path:** set `USE_BEDROCK=true` + AWS creds; the Bedrock client
(`nq_api/llm/`) exposes a `.messages.create()` adapter so all six LLM call
sites work unchanged. Cross-region inference profiles supported. This is the
"run on your own AWS account" path for an acquirer.

**Local demo:** `docker compose up --build` (see README). No keys needed.

## Smoke test

```
python scripts/smoke_test.py        # 15 endpoints; expects SMOKE_TEST_SECRET
```

15/15 pass on healthy deploy. `/query/v2` may time out at 60s — known heavy
endpoint, not a regression by itself.

## Database

- Canonical migrations: `supabase/migrations/001–025` (apply via Supabase SQL
  editor; `db_migrate.py` checks required tables at startup and logs warnings).
- Backups: `scripts/backup_database.py` / `.ps1` (pg_dump + gzip).
- Demo schema for local Postgres is auto-generated: `scripts/export_demo_schema.py`.

## Known limitations (disclosed)

1. **OpenBB cold start** — Render free-tier sleeps; first Terminal request after
   idle takes 30–60s. Mitigated: keep-warm ping every 5 min, 10s connect
   timeout for fast detection, warmup + retry ladder, frontend auto-retry.
   Do not engineer further; an always-on instance solves it with money.
2. **yfinance fragility** — mitigated via `yf_guard` (curl_cffi, retries,
   Render skip) but FMP should remain the primary source. Buyer needs own FMP key.
3. **DII/FII granularity** — market-aggregate proxy, not per-stock.
4. **`/query/v2` deep-dive latency** — multi-agent debate can exceed 60s on
   Render. Recommended evolution: async job + status polling.
5. **Anjali NIFTY200 completeness** — sister-repo Excel currently yields 11 of
   ~200 India rows; ingestion code is correct against available rows.
6. **Render auto-deploy webhook** — fires unreliably; use manual deploy.
