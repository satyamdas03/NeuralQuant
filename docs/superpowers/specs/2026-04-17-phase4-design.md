# NeuralQuant Phase 4 — Design Spec

**Date:** 2026-04-17
**Status:** Approved (user sign-off Apr 17)
**Base commit:** `768d4b2` (Phase 3 / v4.0 — live at neuralquant.vercel.app)
**Target ship:** 8 weeks from start (end of Q2 2026)

---

## 1. Goals

Phase 4 turns NeuralQuant from a live demo into a revenue-capable SaaS with defensible quant depth.

Four pillars, executed in order:

| Pillar | Outcome | Investor-facing win |
|---|---|---|
| A — Auth + Watchlists + Tiers | Users log in, save watchlists, pay for Pro | Closes the 6/10 "monetisation readiness" gap |
| B — Universe Expansion (500 US + 200 NSE, sector-adjusted) | 5× more stocks, more accurate scoring | Product feels 5× more powerful |
| C — Scoring Upgrades (fitted HMM, ISM PMI, Reddit/StockTwits sentiment) | Deeper moat, new factor | Strongest technical differentiation |
| D — Backtesting (backtrader) | "What if I'd followed NeuralQuant 2 years ago?" | Converts curious visitors into paying users |

**Non-goals for Phase 4:**
- Mobile app (Phase 5)
- Options chain (Phase 5)
- WebSocket streaming (Phase 5)
- ASX coverage (deferred — nice-to-have, not blocker)
- X/Twitter sentiment (API too expensive; StockTwits substitutes)

---

## 2. Architecture Overview

```
┌───────────────────────────────────────────────────────────────┐
│  Next.js frontend (apps/web)                                  │
│  /dashboard /watchlist /backtest  (auth-gated)                │
│  /screener /stocks/[t]  (free tier, rate-limited)             │
└──────────────────┬────────────────────────────────────────────┘
                   │ JWT (Supabase) + Stripe checkout
                   ▼
┌───────────────────────────────────────────────────────────────┐
│  FastAPI backend (apps/api)                                   │
│  Dependency: verify_supabase_jwt → user_tier                  │
│  Rate-limit by tier in-memory (slowapi)                       │
│  Routes: /auth/me  /watchlist  /backtest  /webhooks/stripe    │
└──────┬───────────┬──────────────┬─────────────────────────────┘
       │           │              │
       ▼           ▼              ▼
┌───────────┐ ┌───────────┐ ┌────────────────────────┐
│ Supabase  │ │ Scoring   │ │  Backtest engine       │
│ Postgres  │ │ cache     │ │  backtrader + SPY ref  │
│ + Auth    │ │ (Postgres)│ │  async worker          │
│ + RLS     │ │           │ │                        │
└───────────┘ └───────────┘ └────────────────────────┘
       ▲
       │ nightly cron (GitHub Actions)
       ▼
┌───────────────────────────────────────────────────────────────┐
│  Score builder v2                                             │
│  - Sector-adjusted rank (GICS sector, not universe-wide)      │
│  - Fitted HMM regime (pickled model, loaded at boot)          │
│  - Reddit/StockTwits sentiment factor                         │
└───────────────────────────────────────────────────────────────┘
```

---

## 3. Pillar A — Auth + Watchlists + Tiers + Stripe

### 3.1 Supabase setup

- Project: `neuralquant-prod`
- Tables:
  ```sql
  CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    email TEXT UNIQUE NOT NULL,
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free','investor','pro','api')),
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
  );

  CREATE TABLE watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('US','IN')),
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, ticker, market)
  );

  CREATE TABLE usage_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,
    ts TIMESTAMPTZ DEFAULT now()
  );
  CREATE INDEX idx_usage_user_ts ON usage_log(user_id, ts DESC);
  ```
- RLS: users see only their own rows. `service_role` bypasses for backend.
- Trigger: on `auth.users` insert, insert row into `public.users` with tier=`free`.

### 3.2 Tier matrix

| Tier | Price | Screener rows | NL queries/day | PARA-DEBATE/day | Watchlists | Backtest/day |
|---|---|---|---|---|---|---|
| free | $0 | top 10 | 5 | 0 | 1 (5 tickers) | 1 |
| investor | $19/mo | top 50 | 100 | 5 | 5 (20 tickers each) | 10 |
| pro | $49/mo | unlimited | 500 | unlimited | unlimited | unlimited |
| api | $99/mo | + API access 10K calls/mo | unlimited | unlimited | — | unlimited |

### 3.3 Auth flow

- Frontend: `@supabase/ssr` (server components + middleware). Email magic link + Google OAuth.
- Backend: FastAPI dep `get_current_user(request)` — pulls `Authorization: Bearer <jwt>`, verifies with Supabase JWKS, returns `User` model with tier.
- Anonymous routes still work (free tier) — dep returns `None`.

### 3.4 Stripe

- Products: `investor_monthly` ($19), `pro_monthly` ($49), `api_monthly` ($99).
- Checkout: frontend hits `POST /billing/checkout` → backend creates `Checkout.Session` → redirect URL.
- Webhook `/webhooks/stripe` handles: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`. Updates `users.tier` + `subscription_status`.
- Customer portal: `POST /billing/portal` → redirect URL.
- Secret management: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_INVESTOR_PRICE_ID`, `STRIPE_PRO_PRICE_ID`, `STRIPE_API_PRICE_ID` in Render env + Vercel env.

### 3.5 Rate limiting

- `slowapi` with key = `user.id or request.client.host`.
- Per-endpoint limits pulled from `TIER_LIMITS` dict keyed by tier.
- Counter stored in Postgres `usage_log` (not Redis — avoids extra infra). Trade-off: slower check (~20ms), but acceptable and free.

---

## 4. Pillar B — Universe Expansion

### 4.1 Static universe JSON

- `apps/api/src/nq_api/data/sp500.json` — 500 US tickers + GICS sector
- `apps/api/src/nq_api/data/nifty200.json` — 200 NSE tickers + GICS sector
- Source: Wikipedia scrape (one-off, committed). Refresh script `scripts/refresh_universes.py` quarterly.

### 4.2 Sector-adjusted factors

Replace universe-wide cross-sectional rank with within-sector rank:

```python
# score_builder.py v2
def sector_adjusted_rank(df: pd.DataFrame) -> pd.DataFrame:
    """Rank each factor within GICS sector (not universe-wide)."""
    for factor in ["quality", "momentum", "value", "low_vol", "short_interest"]:
        df[f"{factor}_pct"] = df.groupby("sector")[factor].rank(pct=True)
    df["composite_pct"] = df[[f"{f}_pct" for f in FACTORS]].mean(axis=1)
    return df
```

Rationale: a tech stock's 60th percentile quality ≠ a utility's 60th percentile. Academic factor zoo already supports this.

### 4.3 Cached nightly scoring

- **Problem:** 700 live-yfinance calls per screener request = 60s. Unacceptable.
- **Solution:** nightly GitHub Actions cron runs `scripts/precompute_scores.py`:
  1. Loop all 700 tickers, fetch fundamentals via yfinance
  2. Compute factor percentiles + composite + AI score
  3. Upsert to Supabase `score_cache` table
- Screener reads from `score_cache` → sub-100ms response.
- New table:
  ```sql
  CREATE TABLE score_cache (
    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    sector TEXT,
    score_1_10 INT,
    composite_pct REAL,
    quality_pct REAL,
    momentum_pct REAL,
    value_pct REAL,
    low_vol_pct REAL,
    short_interest_pct REAL,
    sentiment_pct REAL,
    regime_id INT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY(ticker, market)
  );
  ```
- Individual stock page still hits live data (only 1 ticker = fast).

### 4.4 Trade-off acknowledged

Screener shows **day-stale** scores. Stock detail page + AskAI use **live** data. Banner on screener: "Composite scores refresh nightly. Click any stock for live data."

---

## 5. Pillar C — Scoring Upgrades

### 5.1 Fitted HMM

- Train `hmmlearn.GaussianHMM(n_components=3)` on 20y FRED series:
  - HY credit spread (BAMLH0A0HYM2)
  - VIX (VIXCLS)
  - 2s10s curve (T10Y2Y)
  - Fed funds (DFF)
- Hidden states map to `{0: Risk-On, 1: Transition, 2: Risk-Off}` by sorted state-mean vol.
- Script: `scripts/train_hmm.py` → `apps/api/src/nq_api/data/hmm_model.pkl`. Retrain monthly.
- Replace current hardcoded regime logic in `score_builder.py` with model.predict on latest row.

### 5.2 ISM PMI

- New FRED series `NAPM` (ISM Manufacturing PMI).
- Additional macro context injected into AskAI for macro questions.
- Added to screener regime context header.

### 5.3 Reddit sentiment factor

- Library: `PRAW` (Reddit API free tier — 60 req/min).
- Daily cron pulls top 100 posts from `r/stocks`, `r/wallstreetbets`, `r/investing`, `r/IndiaInvestments` (last 24h).
- Extract ticker mentions via regex + `apps/api/src/nq_api/data/ticker_aliases.json`.
- Score each post with VADER (`vaderSentiment` package).
- Aggregate: per-ticker `(mention_count, avg_compound_score)`.
- Normalize to percentile → new factor column `sentiment_pct` in score_cache.
- StockTwits supplements (free REST API, no key): `https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json` returns 30 messages with bullish/bearish labels.

### 5.4 Composite score v2

```python
COMPOSITE_WEIGHTS_V2 = {
    "quality": 0.25,
    "momentum": 0.20,
    "value": 0.15,
    "low_vol": 0.15,
    "short_interest": 0.10,
    "sentiment": 0.15,   # NEW
}
```

Regime-conditional tilts retained (Risk-Off → momentum_weight × 0.5, low_vol × 1.5).

---

## 6. Pillar D — Backtesting

### 6.1 Strategy

User picks ticker universe + date range + rebalance frequency. Strategy = **"Long top-N by composite_score, rebalanced monthly, equal-weight."** No shorting in MVP.

### 6.2 Engine

- `backtrader` (solo-dev friendly, mature).
- Data feed: yfinance history, cached in local parquet on first pull.
- Metrics: total return, annualized return, Sharpe, Sortino, max drawdown, win rate, benchmark vs SPY (US) or NIFTYBEES (IN).

### 6.3 Route + worker

- `POST /backtest` body: `{market, top_n, start, end, rebalance}` → returns `job_id`.
- Async worker (FastAPI `BackgroundTasks` for MVP; Celery later if needed).
- `GET /backtest/{job_id}` returns status + results.
- Results persisted in Supabase `backtests` table:
  ```sql
  CREATE TABLE backtests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    market TEXT, top_n INT, start_date DATE, end_date DATE,
    rebalance TEXT,
    status TEXT DEFAULT 'pending',
    equity_curve JSONB,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
  );
  ```

### 6.4 Frontend

- New page `/backtest`: form (market, top-N slider, date range, rebalance freq).
- On submit: POST, poll every 2s for status.
- Result: equity curve (recharts), metrics table, benchmark overlay.

---

## 7. Data Model Summary

New Supabase tables:
- `users` (auth-linked, tier + stripe ids)
- `watchlists` (user_id, ticker, market)
- `usage_log` (rate limiting)
- `score_cache` (nightly precomputed scores)
- `backtests` (results)

New pickle/JSON assets in repo:
- `apps/api/src/nq_api/data/sp500.json`
- `apps/api/src/nq_api/data/nifty200.json`
- `apps/api/src/nq_api/data/ticker_aliases.json`
- `apps/api/src/nq_api/data/hmm_model.pkl` (gitignored; built by cron)

---

## 8. Routes Added

| Method | Path | Auth | Tier gate |
|---|---|---|---|
| GET | `/auth/me` | required | — |
| POST | `/auth/sync` (on signup trigger) | required | — |
| GET | `/watchlists` | required | — |
| POST | `/watchlists` | required | tier limit |
| DELETE | `/watchlists/{id}` | required | — |
| POST | `/billing/checkout` | required | — |
| POST | `/billing/portal` | required | — |
| POST | `/webhooks/stripe` | signature | — |
| POST | `/backtest` | required | tier limit |
| GET | `/backtest/{id}` | required | owner only |
| GET | `/backtest` (list) | required | owner only |

Existing routes get rate-limited via dep: `/screener`, `/query`, `/analyst`, `/stocks/*`.

---

## 9. Environment Variables

Render (backend) + Vercel (frontend):

```
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=      # backend only
SUPABASE_JWT_SECRET=             # backend only

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_INVESTOR_PRICE_ID=
STRIPE_PRO_PRICE_ID=
STRIPE_API_PRICE_ID=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=

# Reddit
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=neuralquant/0.1

# Existing (unchanged)
ANTHROPIC_API_KEY=
FRED_API_KEY=
```

---

## 10. Build Sequence (8 weeks)

| Week | Pillar | Deliverable |
|---|---|---|
| 1 | A | Supabase project, schema, RLS, auth UI (login, signup, logout) |
| 2 | A | Watchlist CRUD, tier rate-limiting, Stripe checkout + webhook |
| 3 | B | Universe JSON (500 US + 200 NSE), sector-adjusted score_builder v2 |
| 4 | B | score_cache table, nightly cron, screener reads from cache |
| 5 | C | Fitted HMM model + train script + integration |
| 6 | C | Reddit + StockTwits sentiment factor, ISM PMI, composite v2 |
| 7 | D | Backtesting route + backtrader engine + `/backtest` page |
| 8 | — | Polish: loading states, error handling, Stripe emails, docs |

---

## 11. Testing Strategy

- **Each pillar ships with tests before merge** (TDD via `superpowers:test-driven-development`).
- Backend: pytest. New: `test_auth.py`, `test_watchlist.py`, `test_billing.py`, `test_scoring_v2.py`, `test_backtest.py`.
- Frontend: Playwright smoke test for auth flow + checkout (Stripe test mode).
- Nightly cron: dry-run target before enabling.
- Manual verification on staging deploy before each merge to main.

---

## 12. Risks + Mitigations

| Risk | Mitigation |
|---|---|
| Supabase vendor lock-in | Schema is portable Postgres — migration path to self-host any time |
| Stripe webhook missed events | Idempotency key on `checkout.session.completed`; reconciliation script `scripts/reconcile_stripe.py` weekly |
| Nightly cron fails silently | GitHub Actions posts to Slack on failure (webhook); fallback to previous day's cache |
| yfinance rate limit on 700 tickers | Batch in groups of 50 with 1s sleep; fall back to `TICKER.NS` second-pass |
| HMM overfitting | Walk-forward validation in `train_hmm.py`; retain current heuristic as fallback if HMM confidence < 0.6 |
| Backtest long-running blocks API worker | `BackgroundTasks` queues off-thread; MVP caps backtest to 5y × top-20 (~10s) |
| Reddit API shutdowns | StockTwits redundant; sentiment factor optional — composite still valid without it |

---

## 13. Success Metrics

**End of Phase 4 (Week 8):**
- 100% of existing Phase 3 functionality unchanged and still passing tests
- 3 paid tiers purchasable via Stripe test + live mode
- Screener renders 500 US + 200 NSE stocks in <1s
- Backtesting page produces equity curve vs SPY for any top-N strategy
- Monetisation readiness: 6/10 → 9/10 (per Report Section 10 scorecard)
- Product completeness: 8/10 → 9/10

---

## 14. Out of Scope (explicit)

- Mobile app (React Native)
- WebSocket streaming price feed
- Options chain integration
- ASX coverage
- X/Twitter API integration
- Multi-currency settlement (Stripe USD only for MVP)
- White-label product
- Payments in INR (Stripe India is supported but requires GST registration — defer to Phase 5)

---

**Ready for implementation plan.** Next step: invoke `superpowers:writing-plans` to decompose Week 1 into concrete tasks.
