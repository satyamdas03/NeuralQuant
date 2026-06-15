<div align="center">

# NeuralQuant

**AI-Powered Stock Intelligence Through Adversarial Multi-Agent Debate**

*Institutional-grade quant engine + PARA-DEBATE multi-agent system + live voice analysts. US + India. 100% live data.*

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs)](https://nextjs.org)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](PROPRIETARY-LICENSE.txt)

> **This codebase is available for acquisition.** Contact the author for details.

**Live at [neuralquant.co](https://neuralquant.co)** · API `neuralquant.onrender.com` (v4.1.0)

</div>

---

## Current Status — June 2026

**Production live.** API v4.1.0, ~950 stocks in the score cache (≈450 US + ≈500 India), nightly refresh healthy. Last full prod smoke (2026-06-15): **13/13 endpoints PASS**, zero JS console errors across the app.

**Recently shipped (Sessions 90–94):**
- **Branding** unified to NeuralQuant; landing, methodology, pricing refreshed.
- **Voice analysts live** — QuantAstra (on-demand) + **Veronica** (page-aware companion with "Hey Veronica" wake word + morning briefing), via a LiveKit worker.
- **Hermes** — autonomous self-improving trading agent surfaced at `/hermes` (live "Matrix" dashboard, SSE log stream).
- **India data parity** — QuantFactor universe expanded from ~60 to ~500 NSE names via a daily-refreshed sheet sync.
- **Security hardening (P0–P6)** — Supabase RLS, log redaction, gitleaks + dependency scanning in CI, IDOR fixes, HTTP security headers + CSP (report-only), per-IP abuse limiting, webhook-signature enforcement, a security-event audit log, and an incident-response runbook. See [Security](#security).
- **QA pass** — fixed a false "loss-making" badge, a CSP console error, and a "Sign In while authenticated" nav bug; removed the unused `/alerts` page.

**Operator follow-ups (not code):** rotate the ElevenLabs key on the voice worker, manual-deploy `nq-api` on Render (ships the latest API/security changes), apply migration `021_security_events.sql`, warm the API before live demos (first-hit cold start on Ask Morgan / PARA-DEBATE is ~45–80s).

---

## Acquisition Overview

**AI-powered stock intelligence platform — India + US.**

Multi-agent Claude-powered research engine (PARA-DEBATE) · QuantFactor quintile engine + proprietary **IRS%** score across ~950 stocks · web + mobile (Expo) + voice (LiveKit) + an autonomous trading agent on one FastAPI backend · Anthropic Claude with an AWS Bedrock path · Q1FY27 documented backtest: **+13.5% avg alpha vs Nifty50, ~89% hit rate** (see [neuralquant.co/methodology](https://neuralquant.co/methodology)).

**18+ months of build. 90+ documented sessions.**

### Evaluate in 15 minutes — zero API keys

```bash
git clone <repo> && cd NeuralQuant
cp .env.example .env          # DEMO_MODE=true is the docker-compose default
docker compose up --build
# → http://localhost:3000
```

The demo stack bundles a real data snapshot (Supabase tables, ~1,669 rows) and a canned PARA-DEBATE output, so the dashboard, screener, stock detail, and backtest pages work offline. Add `ANTHROPIC_API_KEY` to run live agent debates.

### What's included in the sale

Codebase · neuralquant.co domain · Supabase data + Q1FY27 backtest results · scoring methodology IP (IRS%, G Score, Risk Efficiency, QuantFactor quintiles) · sister repo (anjali-value-stocks) · brand/design system · optional 3–6 month founder transition. Full list: [docs/ASSET_INVENTORY.md](docs/ASSET_INVENTORY.md). Due diligence: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/BUG_HISTORY.md](docs/BUG_HISTORY.md) · [docs/OPERATIONS.md](docs/OPERATIONS.md) · [docs/HANDOVER.md](docs/HANDOVER.md). Patent strategy: [IP_PROTECTION/MEETING_PREP.md](IP_PROTECTION/MEETING_PREP.md).

---

## What is NeuralQuant?

A full-stack AI stock intelligence platform that combines a **quantitative signal engine** with a **multi-agent AI analyst debate** (PARA-DEBATE), **natural-language and voice analysts**, and an **autonomous trading agent** — backed entirely by **live, real data**.

### Why It's Different

| Feature | NeuralQuant | Danelfin | TipRanks | Seeking Alpha |
|---------|-------------|----------|----------|---------------|
| **Adversarial agent** | Mandatory BEAR challenge | No | No | No |
| **India market** | ~500 NSE names, live | No | No | No |
| **Natural language queries** | Yes (Ask Morgan) | No | No | No |
| **Voice analyst** | Yes (QuantAstra + Veronica) | No | No | No |
| **LLM hallucination guard** | Per-agent metric reconciliation vs live data | No | No | No |
| **Real-time enrichment** | RSI/MACD/ATR live | End-of-day | End-of-day | End-of-day |
| **Multi-agent debate** | 6 agents + head analyst, 1 verdict | Single score | Aggregation | Single author |
| **Pricing** | Free / $9.99 / $29.99 / $99.99 | Free / $20 / $49 / $99 | Free / $30 / $50 | $239/yr |

> **Expert Assessment (May 2026):** Overall 8.6/10 — Technical Depth 9.2, USP Distinctiveness 9.0, Market Timing 8.4. PARA-DEBATE validated by FinDebate (+20.4% alpha), AlphaAgents (BlackRock), Apex Parliament, and TradingAgents research.

---

## Key Features

- **PARA-DEBATE** — 5 specialist agents (Macro, Fundamental, Technical, Sentiment, Geopolitical) + adversarial BEAR challenge + Head Analyst synthesis, run in parallel (`asyncio.gather`). Each agent's numeric claims are reconciled against live authoritative data before synthesis (hallucination guard). SSE-streamed.
- **Ask Morgan** — natural-language queries with conversation memory and live data injection. *"Is AAPL a buy?"* → price, P/E, IRS%, QuantFactor breakdown, consensus.
- **Voice analysts** — **QuantAstra** (on-demand voice) and **Veronica** (page-aware companion: wake word, morning briefing, reads the page you're on). Deepgram → Claude → ElevenLabs pipeline on a LiveKit worker.
- **QuantFactor engine + IRS%** — cross-sectional quintile scoring (Growth / Return / Valuation / Risk) vs index peers, distilled into the proprietary **Investment Readiness Score (IRS%)**. US + India.
- **Hermes** — autonomous self-improving trading agent (paper). LLM "reflection" loop mutates one strategy variable at a time with a written rationale and version history. Surfaced at `/hermes`.
- **Screener** — filter/rank by IRS%, QuantFactor composite, sector, market; presets.
- **Backtest** — walk-forward validation, Q1FY27 results published on `/methodology`.
- **Dual market** — US (S&P 500) + India (NIFTY 500 pool) with India-specific signals (delivery %, India VIX regime).
- **Payments** — Stripe + PayPal subscriptions, 4 tiers. Free during the development phase.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                  Next.js 16 Frontend (Obsidian Quantum)               │
│  Dashboard · Screener · Stock Detail · Ask Morgan · Portfolio ·       │
│  Watchlist · Hermes · Backtest · Methodology · Veronica (global orb)  │
└───────────────┬───────────────────────────────────────┬──────────────┘
                │ REST / SSE (via /api proxy)            │ LiveKit (wss)
┌───────────────▼───────────────────────────────────┐   │
│                  FastAPI Backend (nq-api)          │   │
│  34 routers · multi-agent debate · 4-tier cache    │   │
│  Security: JWKS auth · RLS · ADMIN_EMAILS gate ·   │   │
│            IP abuse limiter · webhook sig verify ·  │   │
│            log redaction · security_events audit    │   │
│                                                     │   │
│  Stocks/Screener/Analyst/Query/Market/Portfolio ·   │   │
│  Auth/Checkout(Stripe+PayPal)/Webhooks ·            │   │
│  Watchlists/Backtest/Sentiment/Hermes(proxy)/Team   │   │
└──────┬───────────────────┬────────────────┬────────┘   │
       │                   │                │            │
┌──────▼─────┐  ┌──────────▼────────┐  ┌────▼─────────┐  │
│ nq-signals │  │ PARA-DEBATE        │  │ QuantFactor  │  │
│ 5-factor + │  │ 6 agents ∥ +       │  │ quintile eng │  │
│ HMM regime │  │ head analyst       │  │ + IRS% (US/IN│  │
└──────┬─────┘  │ + metric reconcile │  │  daily sync) │  │
       │        └────────────────────┘  └──────────────┘  │
┌──────▼──────────────────────────────┐   ┌───────────────▼──────────────┐
│            nq-data layer             │   │   livekit-agent (worker)     │
│ yfinance · FMP · NSE Bhavcopy · FRED │   │  QuantAstra + Veronica       │
│ EDGAR F4 · Finnhub · OpenBB proxy    │   │  Deepgram→Claude→ElevenLabs  │
└──────────────────────────────────────┘   └──────────────────────────────┘

External: Hermes trading agent (Railway) ──proxied via /hermes──▶ nq-api
```

**Apps:** `apps/web` (Next.js, Vercel) · `apps/api` (FastAPI, Render) · `apps/livekit-agent` (voice worker, Render) · `apps/team` (internal Team Hub, Vercel) · `apps/mobile` (Expo). Packages: `packages/data` (nq-data), `packages/signals` (nq-signals).

---

## Live Endpoints (Verified 2026-06-15 — 13/13 PASS)

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/health` | GET | 200 | `v4.1.0`, ~950 cache rows |
| `/stocks/AAPL?market=US` | GET | 200 | IRS%, ForeCast, factor radar |
| `/stocks/TCS?market=IN` | GET | 200 | India full render incl ₹ prices |
| `/stocks/AAPL/chart?period=1mo` | GET | 200 | OHLCV |
| `/stocks/AAPL/meta` | GET | 200 | Market cap, P/E, beta |
| `/screener/preview?market=US` | GET | 200 | Ranked results |
| `/market/overview` | GET | 200 | 4 indices |
| `/market/sectors` | GET | 200 | 11 sectors |
| `/market/news` | GET | 200 | Headlines + sentiment |
| `/market-wrap/today` | GET | 200 | Daily wrap |
| `/query/v2` (Ask Morgan) | POST | 200 | ~45s cold, fast warm |
| `/analyst/stream` (PARA-DEBATE) | POST | 200 | SSE, ~77s cold |
| `/hermes/status` | GET | 200 | Trading agent state |
| `/auth/me` | GET | 401 | Bearer required |

---

## Data Sources

Every number is sourced from live APIs — no synthetic data.

| Data Point | Source | Refresh |
|---|---|---|
| VIX / India VIX | yfinance `^VIX` / `^INDIAVIX` | Real-time |
| S&P 500 vs 200-day MA | yfinance `^GSPC` | Real-time |
| HY Credit Spread OAS | FRED `BAMLH0A0HYM2` | Daily |
| Profile / quote / fundamentals | FMP (primary) → yfinance (fallback) | Real-time |
| QuantFactor quintiles (IN) | Daily "NSE 100/500 Analysis" sheet sync | Daily |
| P/E TTM / P/B ratio | FMP / yfinance | Real-time |
| Delivery % (India) | NSE Bhavcopy | Daily |
| Insider buying/selling | SEC EDGAR Form 4 | As filed |
| RSI-14, MACD, ATR-14, SMA | Finnhub candles | 15 min |
| News sentiment | FMP → Finnhub → yfinance cascade | 30 min |
| Extended / terminal data | OpenBB proxy (`nq-openbb`) | On demand |

---

## The 5-Factor Model (nq-signals)

Scores are computed cross-sectionally within a reference universe — no hardcoded thresholds.

**US Market:**

| Factor | Signal | Weight (Risk-On) |
|---|---|---|
| **Quality** | Gross margin + Piotroski F-score + Accruals | 25% |
| **Momentum** | 12-1 month price return (Jegadeesh-Titman) | 25% |
| **Value** | Inverse of (P/E rank x 0.5 + P/B rank x 0.5) | 10% |
| **Low Volatility** | Inverse of realized 1Y vol + beta rank | 15% |
| **Short Interest** | Inverse of short float rank | 10% |
| **Insider** | EDGAR Form 4 cluster score | 5% |

**India Market** swaps Short Interest for **Delivery %** (institutional conviction via `delivery_pct` rank). Regime weights shift automatically — US uses a 4-state HMM; India uses India VIX heuristics (VIX > 25 = Bear, > 18 = Late-Cycle, else Risk-On).

> Alongside this, the **QuantFactor engine** scores each name into quintiles (Growth / Return / Valuation / Risk) vs index peers and derives the **IRS%** (Investment Readiness Score) shown across the product.

---

## Security

Hardened across a P0–P6 program (Sessions 92–93):

- **Auth** — Supabase JWT verified via JWKS; admin surfaces gated on an `ADMIN_EMAILS` allowlist (not tier); internal Team Hub behind admin/service-token.
- **Database** — Row-Level Security (migrations `020_enable_rls.sql`, `021_security_events.sql`); backend uses `service_role` with RLS as the net.
- **Secrets** — log redaction filter (scrubs keys/tokens/emails); gitleaks secret scanning in CI; `.env` gitignored.
- **Web** — HTTP security headers (HSTS, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy) + Content-Security-Policy (report-only, pending enforce).
- **Abuse / integrity** — per-IP rate fuse on expensive endpoints (e.g. LiveKit token); Stripe/PayPal webhook signatures verified (fail-closed); file-upload size caps + MIME allow-list; prompt-injection guards on LLM file analysis.
- **Supply chain** — `pip-audit` + `npm audit` + Dependabot in CI.
- **Observability** — `security_events` audit log + incident-response runbook (`docs/SECURITY_INCIDENT_RESPONSE.md`).

Full audit: `docs/SECURITY_IDOR_AUDIT.md` · operator actions: `docs/SECURITY_P0_P1_OPERATOR_ACTIONS.md`.

---

## Pricing

| Tier | USD/mo | INR/mo (approx) | Features |
|------|--------|-----------------|----------|
| **Free** | $0 | ₹0 | PARA-DEBATE, screener, market data |
| **Investor** | $9.99 | ~₹899 | Unlimited PARA-DEBATE, Ask Morgan |
| **Pro** | $29.99 | ~₹2,499 | + Watchlists, backtest, portfolio |
| **API** | $99.99 | ~₹8,499 | Full API access |

All charges in USD via Stripe/PayPal. **Quota enforcement is bypassed during the development phase** (free indefinitely until monetization).

---

## Repository Layout

```
stockpredictor/
├── packages/
│   ├── data/                  # nq-data: connectors, DataBroker, DuckDB store
│   └── signals/               # nq-signals: 5-factor engine, HMM regime, ranker
├── apps/
│   ├── api/                   # FastAPI backend (34 routers)
│   │   ├── src/nq_api/
│   │   │   ├── auth/              # JWT, admin gate, rate_limit, abuse_limit, security_audit
│   │   │   ├── agents/            # PARA-DEBATE agent prompts + context builders
│   │   │   ├── cache/             # score cache, quantfactor cache, enrichment cache
│   │   │   ├── jobs/              # quantfactor_sync, nightly_score, market_refresh
│   │   │   ├── services/          # stock_summary, portfolio, enrichment, clarification
│   │   │   └── routes/            # stocks, screener, analyst, query, hermes, team, ...
│   │   └── migrations/           # SQL migrations (… 020 RLS, 021 security_events)
│   ├── web/                   # Next.js 16 frontend (Vercel)
│   ├── livekit-agent/         # QuantAstra + Veronica voice worker (Render)
│   ├── team/                  # Internal Team Hub (Vercel)
│   └── mobile/                # Expo mobile app
├── scripts/                   # smoke_test.py, exports, backtest, db backup
├── .github/workflows/         # ci, secret-scan (gitleaks), dep-audit, market-refresh, ...
└── render.yaml                # Render service definitions (api + workers)
```

---

## Quickstart

### Prerequisites
Python 3.12+ · [uv](https://github.com/astral-sh/uv) · Node.js 20+ · Anthropic API key (PARA-DEBATE/Ask Morgan) · FRED + Finnhub + FMP keys (data).

### 1. Clone and install
```bash
git clone https://github.com/satyamdas03/NeuralQuant.git
cd NeuralQuant
uv sync
```

### 2. Configure (`apps/api/.env`)
```bash
ANTHROPIC_API_KEY=sk-ant-...
FRED_API_KEY=...
FINNHUB_API_KEY=...
FMP_API_KEY=...
SUPABASE_URL=...           SUPABASE_SERVICE_ROLE_KEY=...   SUPABASE_ANON_KEY=...
ADMIN_EMAILS=you@example.com
# Payments (optional): STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PAYPAL_*
# Voice (optional, on the livekit-agent worker): LIVEKIT_*, DEEPGRAM_API_KEY, ELEVENLABS_API_KEY
# USE_BEDROCK=true to route Claude calls through AWS Bedrock
```

### 3. Run
```bash
# API
cd apps/api && ../../.venv/bin/uvicorn nq_api.main:app --reload --port 8000
# Web
cd apps/web && npm install && npm run dev    # http://localhost:3000
```
API at `http://localhost:8000` · Swagger at `/docs`.

### 4. Tests + smoke
```bash
uv run pytest apps/api/tests/ packages/ -v
python scripts/smoke_test.py --api https://neuralquant.onrender.com   # 13 endpoints
```

---

## Deployment

| Service | Platform | URL / Notes |
|---------|----------|-------------|
| **API** (`nq-api`) | Render (Docker) | `neuralquant.onrender.com` — **manual deploy** (auto-deploy unreliable) |
| **Web** | Vercel | [`neuralquant.co`](https://neuralquant.co) |
| **Voice** (`quantastra-agent`) | Render (worker) | LiveKit; holds `ELEVENLABS_API_KEY` |
| **OpenBB** (`nq-openbb`) | Render | Terminal/extended data proxy |
| **Team Hub** | Vercel | Internal ops board |
| **Hermes** | Railway | External trading agent, proxied via `/hermes` |
| **Database** | Supabase | Postgres + Auth + RLS |
| **Payments** | Stripe + PayPal | Subscriptions + verified webhooks |
| **CI/CD** | GitHub Actions | lint, gitleaks, dep-audit |

Scheduling runs via an **in-process scheduler** (02:00 / 02:30 / 20:30 UTC) — nightly score refresh, QuantFactor sync, EOD market wrap.

---

## Competitive Position

> Independent expert assessment (May 2026): Overall 8.6/10, USP Distinctiveness 9.0/10.

| Dimension | Score | Meaning |
|-----------|-------|---------|
| **Technical Depth** | 9.2 | Academic quant rigour, PARA-DEBATE, zero synthetic data |
| **USP Distinctiveness** | 9.0 | Dual-market + adversarial AI + voice + metric reconciliation |
| **Market Timing** | 8.4 | India 90M+ Demat accounts, AI cost deflation |
| **GTM Readiness** | 7.8 | Product live, acquisition channels needed |
| **Investor Readiness** | 7.2 | Pre-revenue; backtest documented, not multi-year |

**Market opportunity:** $47B TAM (global retail fintech analytics), $3.2B SAM (India + US AI tools), $48M SOM.

---

## Roadmap

### Completed
- [x] Quant signal engine (5 factors, HMM regime) + QuantFactor quintile engine + IRS%
- [x] PARA-DEBATE (parallel agents + metric reconciliation) + SSE streaming
- [x] 100% live data (yfinance, FMP, FRED, NSE, EDGAR, Finnhub, OpenBB)
- [x] Auth, tiers, screener, portfolio, watchlist, Stripe + PayPal
- [x] Voice analysts (QuantAstra + Veronica)
- [x] Hermes live trading dashboard
- [x] India data parity (~500 NSE names)
- [x] Security hardening P0–P6 (RLS, headers, rate-limiting, audit log, CI scanning)

### In progress / next
- [ ] Flip CSP from report-only to enforce (after collecting violation reports)
- [ ] Cut PARA-DEBATE / Ask Morgan cold-start latency (keep-warm)
- [ ] Multi-year backtest with published P&L / Sharpe / IC
- [ ] Fitted HMM for India regime (currently heuristic)
- [ ] Test coverage expansion

---

## Known Limitations

1. **Cold-start latency** — first-hit Ask Morgan ~45s, PARA-DEBATE ~77s (warm after). Pre-warm before live demos.
2. **Render manual deploys** — `nq-api` auto-deploy has been unreliable; deploy manually.
3. **CSP report-only** — security headers shipped; CSP not yet enforced (no violation collector yet).
4. **India fundamentals gaps** — some FMP endpoints are US-only; IN relies on the sheet sync + yfinance.
5. **QuantFactor "earnings declined" flag** — derived from profit-growth, not profit level; corrected in UI, full DB correction needs a re-sync.
6. **No persistent Ask Morgan memory** — sliding-window context, lost on refresh.

---

## License

**Proprietary.** See [PROPRIETARY-LICENSE.txt](PROPRIETARY-LICENSE.txt). This codebase is offered for acquisition; not open source.

---

<div align="center">

**Quant Engine + IRS% · PARA-DEBATE Multi-Agent Debate · Voice Analysts · Autonomous Trading Agent · India & US · 100% Live Data**

[neuralquant.co](https://neuralquant.co) · [GitHub](https://github.com/satyamdas03/NeuralQuant) · [API Docs](https://neuralquant.onrender.com/docs)

</div>
