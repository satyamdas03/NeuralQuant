# NeuralQuant — Architecture

Buyer-facing technical map. Verified against the codebase at tag `v4.1.0-sale-ready`.

## Repo layout (uv workspace monorepo)

```
apps/api/            FastAPI backend (nq_api) — 33 routers, agents, jobs, auth, cache
apps/web/            Next.js 16 frontend (33+ pages, App Router)
apps/mobile/         React Native / Expo app (5-tab)
apps/livekit-agent/  QuantAstra voice agent (LiveKit + Deepgram + ElevenLabs)
packages/data/       nq_data — all market data connectors + yf_guard gateway
packages/signals/    nq_signals — factor engine, HMM regime, scoring
supabase/migrations/ Canonical SQL migrations (001–025)
docker/              Demo stack: initdb schema + seed, PostgREST nginx proxy
data/demo_snapshot/  Bundled CSV snapshot (5 tables, 1,669 rows) + sample PARA-DEBATE
scripts/             Smoke test, snapshot export, DB backup, quarterly test
```

## Routers (33, mounted in `apps/api/src/nq_api/main.py`)

| Group | Routers |
|-------|---------|
| Core data | stocks, screener, market, sentiment, newsdesk, terminal |
| AI | analyst (PARA-DEBATE), query (Ask AI v1/v2/v3), share |
| Trading | backtest, broker, live, live_dashboard, testing (quarterly) |
| Users | auth, watchlists, alerts, referral, session, astra_portfolio, mobile |
| Payments | checkout (PayPal), checkout_stripe, paypal_webhook, stripe_webhook |
| Ops | cron, analytics, analytics_track, market_wrap, slack, team, auth_webhook, livekit_token |

## PARA-DEBATE engine (`nq_api/agents/`)

Five specialist agents run in parallel (`asyncio.gather`), then an adversarial
BEAR agent challenges the consensus, then a Head Analyst synthesizes a verdict:

```
MACRO ──────────┐
FUNDAMENTAL ────┤
TECHNICAL ──────┤  parallel        ADVERSARIAL          HEAD ANALYST
SENTIMENT ──────┤  (asyncio) ────► (mandatory bear ────► (verdict + thesis +
GEOPOLITICAL ───┘                   challenge)            consensus clamp)
```

Engineering hardening baked in (see BUG_HISTORY.md):
- **Metric validation**: every number an agent cites is checked against the
  injected `[VERIFIED]` platform data; hallucinated metrics are stripped.
- **Consensus clamping**: head analyst verdict bounded by specialist agreement.
- **Per-agent timeouts** (`nq_api/timeouts.py`): specialists 55s, adversarial 45s.
- **LLM routing**: direct Anthropic API or AWS Bedrock (`USE_BEDROCK=true`),
  via a `.messages.create()`-compatible Bedrock adapter (cross-region profiles).

## Quant scoring

**5-factor engine** (`packages/signals`): Quality, Momentum, Value,
Low-Volatility, Short-Interest (US) / Delivery % (IN). Rank-based percentiles →
composite → 1–10 score. HMM 4-state market regime (separate US and IN macro
feature sets) reweights factors per regime.

**Anjali / IRS% system** (sister-repo ingestion → `anjali_enrichment` +
`quantfactor_universe` tables):
- **G Score** = growth + return + valuation components, range −12..+12
- **Risk Efficiency** = risk × 2, range −8..+8
- **IRS%** = (G + RiskEff + 20) / 40 × 100 — single 0–100 ranking
- Quintile engine over 1,750+ stocks (S&P 500/400/600 + NIFTY 200)

**Quarterly testing framework** (`quarterly_test_runs` / `quarterly_test_results`
tables + `scripts/`): pool selection by IRS% filters, entry snapshots, vs-NIFTY50
alpha measurement. Q1FY27 first run: +12.7% to +14.8% alpha, 87–91% hit rate.

## Data pipeline (tiered fallbacks)

```
Tier 1  FMP Premium      primary US fundamentals/quotes/movers ($49/mo)
Tier 2  yfinance         via yf_guard ONLY (curl_cffi impersonation, retries,
                         hard timeouts, Render-IP skip) — packages/data/.../yf_guard.py
Tier 3  Finnhub          technicals, insider sentiment, news (free tier)
Tier 4  NSE Bhavcopy     India EOD + delivery % (session-cookie handling)
Tier 5  FRED / EDGAR     macro series / insider Form 4
Tier 6  score_cache      Supabase snapshot — always-available last resort
```

Key invariants (enforced by `apps/api/tests/test_market_branching.py`):
- Cache keys are ALWAYS bare tickers (`RELIANCE`, never `RELIANCE.NS`).
- yfinance symbols for IN get `.NS` appended exactly once; US never suffixed.
- IN regime uses IN macro features (`nifty_return_1m` is canonical).

## Persistence

Supabase Postgres accessed via **PostgREST REST** (direct httpx — the supabase-py
SDK caused `RemoteProtocolError` under uvicorn). Single source of truth for
column names: `nq_api/db_columns.py`. The demo stack reproduces the same REST
surface locally (postgres → PostgREST → nginx `/rest/v1` proxy), so zero code
changes between demo and production.

## Cross-cutting middleware

- `NaNSanitizerMiddleware` (main.py): no route can 500 on NaN/Inf JSON.
- Tier quota + rate limiting (`nq_api/auth/rate_limit.py`), guest UUID-v5 IDs.
- `/health` exposes `score_cache_age_hours` + row count for staleness monitoring.
- In-process cron scheduler (main.py lifespan) + Render cron services (render.yaml).

## Demo mode

`DEMO_MODE=true` → serve cache-only, skip live fetch tiers; `/analyst` without an
LLM key returns the bundled `sample_paradebate_RELIANCE.json` with `demo: true`.
`docker compose up` = db (seeded) + postgrest + rest-proxy + api + web.
