# NeuralQuant — Full System Design Specification
**Date:** 2026-03-23
**Status:** Approved
**Author:** AI-assisted design (Claude + 4 research agents)

---

## 1. Vision & Problem

### 1.1 The Problem
Retail investors globally — 60M+ active in India alone, 100M+ in the US — make investment decisions based on CNBC noise, WhatsApp tips, and gut feel. Institutional investors have access to Goldman Sachs research, Bloomberg terminals, and quant teams. Retail does not. The information asymmetry is enormous and growing.

Existing tools fall into two camps:
- **Data screeners** (Finviz, Screener.in, TradingView) — powerful but require financial expertise to interpret; no AI reasoning
- **AI score tools** (Danelfin, Kavout) — opaque black-box scores, US-only, no explanations, not conversational

**No tool exists that combines AI-powered stock research spanning US + Indian markets with institutional-grade analysis, transparent reasoning, and a retail-accessible price point.**

### 1.2 The Solution: NeuralQuant
NeuralQuant is a global AI equity research platform. A 7-agent Claude-powered research team — modeled on how an actual investment research desk works — analyzes stocks across US, India, and global markets each quarter. It produces ranked picks with institutional-grade dossiers, validated against historical outcomes, Wall Street consensus, and live paper trading. Accessible to retail investors at $29/month.

### 1.3 Core Insight
The most important architectural decision: include an **ADVERSARIAL agent** that steelmans the bear case on every top pick. This prevents the system from herding into consensus (the dominant failure mode of analyst teams), builds user trust through transparency, and is completely absent from every competitor.

---

## 2. Architecture Overview — 5 Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 5: Product & Monetization                                 │
│  Next.js 15 (Stitch UI) · Supabase · Stripe · Vercel + Railway  │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: Validation Engine                                      │
│  Backtest (16Q+) · Paper Trading Tracker · Wall St Cross-Check   │
│  Brier-Score Calibration · Quarterly Accuracy Leaderboard        │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: 7-Agent Claude Research Team (PARA-DEBATE)             │
│  MACRO · FUND · TECH-QUANT · SENTIMENT · GEO-REG                │
│  QUANT-RANK · ADVERSARIAL · HEAD ANALYST (synthesis)            │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Signal Engine                                          │
│  10 Quant Signals · LightGBM LambdaRank · 4-Regime HMM          │
│  FinBERT NLP · V8 Logic (evolved) · India-specific signals       │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Data Pipeline (100% free-tier to start)               │
│  yfinance · NSE Bhavcopy · FRED · EDGAR · GDELT · Google News   │
│  StockTwits · PRAW · NSE Options · FINRA Short Int · Screener.in │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack

### 3.1 Frontend
- **Framework:** Next.js 15 (App Router)
- **UI Generation:** Google Stitch (Gemini 2.5 Pro)
- **Component Library:** shadcn/ui + TailwindCSS
- **Charts:** Recharts + TradingView Lightweight Charts widget
- **Auth:** Clerk
- **State:** Zustand
- **Data Fetching:** React Query (TanStack Query v5)
- **Design Language:** Dark-first (#0f0f1a), conviction-coded colours (GREEN=HIGH, PURPLE=MED, AMBER=SPEC, RED=risk)

### 3.2 Backend
- **API:** FastAPI (Python 3.12)
- **AI Orchestration:** Anthropic SDK (Claude claude-opus-4 + claude-sonnet-4)
- **ML Ranker:** LightGBM (LambdaRank, pairwise loss)
- **NLP:** FinBERT (HuggingFace transformers) for earnings call sentiment
- **Technical Indicators:** TA-Lib + pandas-ta
- **Async Jobs:** Celery + Redis
- **Scheduler:** APScheduler (data refresh cron)
- **Regime Detection:** hmmlearn (Hidden Markov Model, 4 states)

### 3.3 Infrastructure
- **Database:** Supabase (PostgreSQL + Row-Level Security)
- **Analytics Store:** DuckDB (dev) → TimescaleDB (production)
- **Cache:** Redis (API responses, agent context, rate-limit token buckets)
- **Frontend Hosting:** Vercel
- **Backend Hosting:** Railway
- **Billing:** Stripe (metered subscriptions)
- **Email:** Resend
- **Monitoring:** PostHog (analytics) + Sentry (errors)

### 3.4 Auth & Access Control Flow

```
1. User signs up via Clerk (email/Google/GitHub)
2. Clerk issues JWT → stored in browser cookie
3. On each API request: Next.js passes JWT in Authorization header
4. FastAPI middleware validates JWT via Clerk JWKS endpoint
   (GET https://api.clerk.com/v1/jwks → cache public keys, verify signature locally)
5. Stripe webhook (customer.subscription.updated) → Supabase user_entitlements table update
6. FastAPI middleware reads Supabase user_entitlements to determine tier:
   FREE | PRO_GLOBAL | PRO_INDIA | ENTERPRISE
7. Route-level guards enforce tier. Rate limit headers returned on every response:
   X-RateLimit-Tier, X-RateLimit-Remaining, X-RateLimit-Reset

Tier enforcement per route:
  GET /api/picks/quarterly         → FREE (Top 3), PRO+ (all 15)
  GET /api/stocks/{ticker}/dossier → FREE (3/day), PRO+ (unlimited)
  POST /api/chat                   → FREE (5 msg/day), PRO+ (unlimited)
  GET /api/portfolio/blueprint     → PRO+ only
  GET /api/validate/leaderboard    → PUBLIC
  GET /api/signals/{ticker}        → PRO+ only
  POST /api/analysis/run           → ENTERPRISE only
```

### 3.5 Core API Contract

Base URL: `https://api.neuralquant.ai/v1`

| Method | Endpoint | Auth | Response Shape |
|--------|----------|------|----------------|
| GET | `/picks/quarterly?market=US\|IN\|ALL&quarter=2026-Q1` | Public (limited) / Pro (full) | `{picks: Pick[], regime: RegimeState, generated_at: ISO8601}` |
| GET | `/stocks/{ticker}/dossier` | Pro | `{ticker, agents: AgentReport[], signals: SignalValues, conviction: Tier, thesis, risk}` |
| GET | `/stocks/{ticker}/signals` | Pro | `{ticker, signal_values: Record<SignalName, number>, regime_weights: RegimeWeights}` |
| POST | `/chat` | Free (5/day) / Pro | `{message: string, context?: {ticker?: string}}` → SSE stream |
| GET | `/validate/leaderboard` | Public | `{quarters: QuarterResult[], win_rates: TierWinRates, vs_benchmarks: BenchmarkComparison}` |
| GET | `/portfolio/blueprint` | Pro | Request: `{picks: TickerList, total_capital: number}` → `{allocations: Allocation[], expected_return_range, max_drawdown_est}` |
| GET | `/market/regime` | Public | `{regime: 1\|2\|3\|4, label: string, confidence: number, indicators: MacroPulse}` |
| POST | `/alerts/subscribe` | Pro | `{ticker: string, condition: AlertCondition}` → `{alert_id: string}` |

Key types:
```typescript
type Tier = 'HIGH' | 'MEDIUM' | 'SPECULATIVE'
type RegimeState = { id: 1|2|3|4; label: string; confidence: number; factor_weights: Record<string, number> }
type AgentReport = { agent: AgentName; score: number; rationale: string; flags: string[] }
type SignalValues = Record<SignalName, { value: number; percentile: number; direction: 'bullish'|'bearish'|'neutral' }>
type Pick = { ticker: string; market: 'US'|'IN'|'GLOBAL'; conviction: Tier; position_size_pct: [number, number]; thesis: string; primary_risk: string; agent_agreement: number; score: number }
```

### 3.6 Monorepo Structure
```
neuralquant/
├── apps/
│   ├── web/              # Next.js 15 frontend
│   ├── api/              # FastAPI backend
│   └── worker/           # Celery async jobs
├── packages/
│   ├── agents/           # 7 Claude agent definitions + prompts
│   ├── signals/          # Quant signal library (10 factors, evolved V8)
│   ├── data/             # Data pipeline (20+ source connectors)
│   ├── ml/               # LightGBM ranker + FinBERT NLP pipeline
│   └── shared/           # Types, schemas, Pydantic models, utils
├── scripts/
│   ├── backtest/         # Historical validation runner
│   └── paper-trade/      # Live prediction tracker
├── policies/             # SEBI compliance docs + disclaimers
└── docs/                 # Architecture docs, design specs (GitHub-facing)
```

---

## 4. Signal Engine (Layer 2)

### 4.1 The 10-Signal Stack
All signals use free data sources. Listed by Information Coefficient (IC) — predictive power measured as rank correlation between predicted and actual returns.

| Rank | Signal | IC Score | Data Source | Notes |
|------|--------|----------|-------------|-------|
| 1 | LightGBM LambdaRank (ML ranker on all factors) | 0.08–0.12 | Built on signals 2–10 | Primary model |
| 2 | Earnings Surprise + Post-Earnings Drift (PEAD) | 0.07–0.10 | SEC EDGAR 8-K | Most robust anomaly |
| 3 | Short Interest (days-to-cover ratio) | 0.05–0.09 | FINRA (free, bi-monthly) | Negative predictor |
| 4 | Quality Composite (Piotroski F-score + Gross Profitability + Accruals) | 0.06–0.08 | EDGAR XBRL / Screener.in | Most portable factor globally |
| 5 | Insider Cluster Buys (SEC Form 4, officers/directors) | 0.05–0.08 | SEC EDGAR (free, T+2) | ~5-8% 6-month abnormal return |
| 6 | Momentum 12-1 with crash-protection filter | 0.05–0.07 | yfinance (free) | Disabled in Regime 3 (bear) |
| 7 | Earnings Call NLP Tone Delta (FinBERT) | 0.03–0.05 | Seeking Alpha free-tier (24-48hr delay) + company IR website scraping | Near-zero correlation with price factors → pure additive alpha. Note: EDGAR does not host earnings call transcripts. Use Seeking Alpha delayed free transcripts or IR site scraping. Real-time transcripts require paid Refinitiv/FactSet. |
| 8 | Institutional Ownership Delta (13F quarter-over-quarter) | 0.03–0.06 | SEC EDGAR 13F (free) | 45-day lag |
| 9 | Put/Call Ratio + Options Flow | 0.04–0.08 | yfinance options / NSE Options API | Contrarian + directional |
| 10 | Low Volatility / Beta-Adjusted Beta (BAB) factor | 0.04–0.06 | yfinance (free) | Overweighted in Regime 3 |

**India-specific additional signals:**
- Promoter buying (SEBI SAST filings) — equivalent of insider signal, historically strong
- FII/DII net flows — foreign institutional flow predicts Nifty direction
- NSE Delivery % — % of volume delivered vs. speculative (unique to NSE, free)
- F&O rollover data — futures/options rollover % predicts short-term price direction
- AMFI monthly fund disclosures — equivalent of US 13F but monthly (faster signal)
- NSE bulk/block deals — institutional print at specific price = support/resistance

### 4.2 4-Regime HMM Engine
Regime is detected using a Hidden Markov Model on 5 macro indicators: VIX level, VIX 20-day change, SPX 200-day MA gap, HY credit spreads (OAS), ISM PMI. Output is a soft probability vector (not hard classification) across 4 regimes.

| Regime | Conditions | Factor Weights |
|--------|-----------|---------------|
| 1 — Risk-On/Trending | VIX <18, SPX above 200MA, spreads tight | ↑ Momentum, Growth, Quality · ↓ Low Vol, Value |
| 2 — Late Cycle/Overheating | VIX 18–24, PMI decelerating, yields rising | ↑ Value, Short Duration, Dividend · ↓ High PE Growth |
| 3 — Stress/Bear | VIX >25, SPX below 200MA, spreads widening | ↑ Low Vol, Quality, Defensives · ↓ Momentum, High Beta |
| 4 — Recovery | VIX declining from >30, spreads tightening, PMI troughing | ↑ Small Cap, Value, Cyclicals · ↓ Defensives |

**Regime Uncertainty Flag:** If MACRO agent cannot classify regime with >60% confidence, all picks auto-downgrade to SPECULATIVE tier until regime clarifies.

---

## 5. The 7-Agent Research Team (Layer 3)

### 5.1 Agent Roster

| Agent | Model | Role |
|-------|-------|------|
| MACRO | claude-opus-4 | Global macro regime identification, central bank policy, yield curve, PMI, sector tilts |
| FUND | claude-sonnet-4 | Bottom-up quality screening, 8-quarter financials, Beneish M-score (earnings manipulation) |
| TECH-QUANT | claude-sonnet-4 | Price momentum, options flow, short interest, relative strength |
| SENTIMENT | claude-sonnet-4 | News NLP, earnings call tone, social sentiment (Reddit, StockTwits), 90-day narrative arc |
| GEO-REG | claude-sonnet-4 | Regulatory pipeline, geopolitical risk, sanctions, antitrust, ESG controversy |
| QUANT-RANK | claude-sonnet-4 | Aggregates all Phase 1 outputs → cross-stock ranking → preliminary Top 20 |
| ADVERSARIAL | claude-opus-4 | Steelman the bear case for every Top 20 stock — prevents consensus herding |

**Head Analyst:** claude-opus-4. Reads all outputs, resolves conflicts, produces final Top 15 with conviction tiers and position sizes.

**Why 7 agents:** Research on prediction tournaments (Good Judgment Project) shows diminishing returns past 7 structurally differentiated perspectives. Teams of 3 are too prone to herding; teams of 9+ create redundancy without accuracy gains.

### 5.2 PARA-DEBATE Protocol

```
Phase 0 (5 min):  Orchestrator pre-screens 200 stocks → 80 candidates
                  (Tier A: top 40 full data; Tier B: next 40 abbreviated; bottom 40 headlines-only)

Phase 1 (15-20 min, parallel):
  MACRO    → Regime report + sector tilts
  FUND     → Quality tiers + earnings quality flags
  TECH     → Momentum/reversal signals + options market structure
  SENTIMENT → Sentiment scores + narrative momentum
  GEO-REG  → Risk flag severity (Low/Med/High/Critical)

Phase 2 (5 min):  QUANT-RANK aggregates → Preliminary Top 20 (structured JSON)

Phase 3 (10 min): ADVERSARIAL reads Top 20 + all reports → bear cases for each

Phase 4 (5 min):  FUND + TECH-QUANT may rebut specific bear cases (300 words max each)

Phase 5 (10 min): HEAD ANALYST reads all → Final Top 15 with:
                  - Conviction tier (HIGH/MEDIUM/SPECULATIVE)
                  - Position size range (5-7% / 3-5% / 1-3%)
                  - Primary thesis (1 sentence)
                  - Primary risk (1 sentence)
                  - Cash allocation if <15 quality picks found

Total runtime: ~50 min serial, ~25 min with parallel async execution
```

### 5.3 Agent Input/Output Contracts

**Phase 1 Specialist Agent — Input Data Packet (per stock, ~6,800 tokens for Tier A):**
```json
{
  "ticker": "NVDA",
  "market": "US",
  "data_as_of": "2026-03-23",
  "price_data": { "ohlcv_1y_daily": [...], "volume_avg_30d": 45000000, "52w_high": 974.0, "52w_low": 462.0 },
  "fundamentals": { "pe_ttm": 38.2, "pb": 22.1, "roe": 0.91, "gross_margin": 0.744, "fcf_yield": 0.021, "revenue_growth_yoy": 0.122, "debt_equity": 0.42, "piotroski_score": 7, "accruals_ratio": -0.03 },
  "signals": { "momentum_12_1": 0.82, "short_interest_pct": 0.023, "insider_net_buys_90d": 3, "institutional_delta_qoq": 0.02, "put_call_ratio": 0.72 },
  "sentiment": { "news_headlines_90d": [...], "earnings_call_tone_delta": 0.12, "reddit_mention_7d": 420, "stocktwits_bullish_pct": 0.67 },
  "macro_context": { "regime_id": 1, "regime_confidence": 0.84, "sector_relative_strength": 1.14 },
  "geo_reg_flags": []
}
```

**Phase 1 Specialist Agent — Output Schema (JSON, max 300 tokens/stock):**
```json
{
  "ticker": "NVDA",
  "agent": "FUND",
  "score": 82,
  "direction": "bullish",
  "rationale": "Strong FCF generation, minimal accruals (Piotroski 7/9), margins expanding. Key risk: valuation premium requires continued AI capex tailwind.",
  "flags": ["high_pe_premium"],
  "confidence": 0.78
}
```

**QUANT-RANK — Input:** Array of Phase 1 outputs (all agents, all Tier A stocks). **Output:** `{ preliminary_top_20: [{ ticker, composite_score, agent_scores: {}, rank }] }`

**ADVERSARIAL — Output per stock:** `{ ticker, bear_thesis: string, probability_thesis_wrong: number, crowding_risk: number, resolved: false }`

**HEAD ANALYST — Output (Final):** Full `quarterly_picks` records matching DB schema in Section 6.3.

**Epistemic Independence Rule:** Phase 1 agents receive identical data packets but never see each other's outputs. Independence is preserved until Phase 2, maximizing signal diversity.

**Context Window Management:** Each specialist agent processes 25–30 stocks per batch (25 × ~6,800 tokens = ~170K tokens, leaving buffer for prompts + output). A 200-stock universe runs in 8 parallel batches. QUANT-RANK and HEAD ANALYST operate on compressed JSON summaries (~500 tokens/stock), enabling full-universe synthesis in one context window.

### 5.3 Confidence Scoring

Three tiers with empirically anchored win rate targets:

| Tier | Win Rate Target | Position Size | Conditions |
|------|----------------|---------------|------------|
| HIGH CONVICTION | >65% quarterly alpha | 5–7% | All 5 specialist agents bullish, bear case resolved, no GEO-REG flag |
| MEDIUM CONVICTION | >52% quarterly alpha | 3–5% | 4/5 agents bullish or 5/5 with minor unresolved bear case |
| SPECULATIVE | >40% quarterly alpha | 1–3% | 3/5 agents bullish, or macro regime uncertain |

Confidence score formula:
```
# Base score (weights sum to 1.0)
# GEO-REG contributes positively (low risk = high score) + penalty component
Score = (FUND×0.30) + (TECH×0.20) + (SENTIMENT×0.15) + (MACRO×0.25) + (GEO_REG_positive×0.10)
      + GEO_REG_penalty (-5/-15/-40 for Med/High/Critical severity)
      + ADVERSARIAL_haircut (0/-10/-50 for Resolved/Unresolved/BrokenThesis)
      + CROWDING_penalty (-8 if in top-10 most common HF holdings)

# GEO_REG_positive: score of 1.0 if no flags, 0.5 if LOW severity flag, 0.0 if any higher severity
# Note: The 5/5 agreement count in tier conditions refers to the 5 Phase 1 specialist agents
# (MACRO, FUND, TECH-QUANT, SENTIMENT, GEO-REG) only. QUANT-RANK, ADVERSARIAL, and HEAD
# ANALYST are synthesis roles and are excluded from the agreement ratio.
```

**Brier-Score Calibration:** After each quarter, per-tier Brier scores are computed. If HIGH CONVICTION wins at only 55% vs 65% target, the tier threshold auto-tightens (e.g., 75 → 82 points required). This prevents "high confidence" from becoming meaningless.

### 5.4 Agent Feedback Loop

Agent weights are adjusted quarterly using rolling exponential Brier scoring:
```python
rolling_brier_A = 0.7 * rolling_brier_A_prev + 0.3 * brier_score_A_quarter
skill_A = max(0, 1 - (rolling_brier_A / 0.25))  # 0.25 = random baseline
weight_A = skill_A / sum(skill_all_agents)
# Floor: no agent drops below 5% weight unless suspended by human review
```

**3-Quarter Underperformance Protocol:** Auto-reduce to 50% baseline weight (rolling Brier handles this automatically). Quarter 5: raise Review Flag for human inspection. If no fixable issue found after 4 consecutive quarters at Brier >0.30, agent is suspended and weight redistributed.

---

## 6. Data Pipeline (Layer 1)

### 6.1 Complete Source Catalog

**Price & OHLCV:**
- `yfinance` — US + India (.NS/.BO) + global, free, 15-min delayed intraday
- Twelve Data — 800 credits/day free, near-real-time, WebSocket streaming for top 50
- NSE Bhavcopy — official NSE EOD CSV, completely free, includes delivery %
- BSE Bhavcopy — official BSE EOD CSV, completely free
- Polygon.io — US EOD on free tier; upgrade to $29/mo Starter for intraday when ready

**Fundamentals:**
- SEC EDGAR XBRL API — ground truth US financials, completely free, unlimited
- Financial Modeling Prep — 250 req/day free, US fundamentals, P/E, P/B, margins
- Screener.in scraper — India's definitive free fundamental source, NSE/BSE all companies

**Macro:**
- FRED API — 800K+ series, unlimited free, US macro (VIX, yields, spreads, CPI, GDP)
- World Bank API — global GDP/inflation/trade, free, annual cadence
- RBI data downloads — India policy rates, CPI, forex reserves, INR data

**News & Sentiment:**
- GDELT Project — global news, 15-min updates, completely free, BigQuery integration
- Google News RSS — `feedparser`, free, near-real-time
- Reddit PRAW — 60 req/min free, r/wallstreetbets + r/IndiaInvestments
- StockTwits — 200 req/hr free, real-time bullish/bearish labels
- NewsAPI — 100 req/day free (development/backtesting use)

**Alternative Signals:**
- SEC EDGAR Form 4 — insider trades, free, T+2, all US companies
- SEC EDGAR 13F — institutional holdings, free, quarterly +45-day lag
- FINRA short interest — bi-monthly bulk file, free
- NSE bulk/block deals — exchange source, free, real-time
- SEBI SAST filings — India promoter/institutional disclosures, free

**Options:**
- yfinance options chain — US options, free, 15-min delayed
- NSE Options Chain API — India NIFTY/BANKNIFTY/stocks, free, real-time

### 6.2 Refresh Schedule

| Frequency | Data | Source |
|-----------|------|--------|
| Every 1 min (market hours) | Top 50 US + Nifty 50 live prices, NSE options PCR/Max Pain, StockTwits spikes | Twelve Data WS · NSE API · StockTwits |
| Every 15 min | Extended universe OHLCV (US 500 + India 100), Google News headlines, VIX, USD/INR | Twelve Data · yfinance · feedparser |
| Every hour | Reddit sentiment, Treasury yield curve, GDELT aggregates, sector indices | PRAW · FRED · GDELT · NSE |
| Daily (post-market) | Full universe OHLCV, NSE Bhavcopy + delivery data, SEC Form 4, FII/DII flows, India bulk deals | yfinance · NSE · EDGAR |
| Weekly | FINRA short interest, promoter pledging, Screener.in fundamentals, M2 + credit spreads | FINRA · Trendlyne · Screener.in · FRED |
| Quarterly (event-triggered) | EDGAR XBRL fundamentals, 13F holdings, India quarterly results, World Bank macro, RBI policy | EDGAR · Screener.in · World Bank · RBI |

**Storage:** DuckDB (dev, zero-config columnar) → TimescaleDB/Supabase (production time-series). Centralized `DataBroker` class manages per-source token buckets — no direct API calls from signal code.

### 6.3 Core Database Schema (Supabase / PostgreSQL)

```sql
-- Core entities
stocks(id, ticker, name, market, sector, market_cap_usd, is_active, created_at)
quarterly_runs(id, quarter, started_at, completed_at, regime_id, status, total_stocks_analyzed)
quarterly_picks(id, run_id, stock_id, conviction_tier, score, position_size_min, position_size_max, thesis, primary_risk, agent_agreement_count, created_at)

-- Signal values (one row per stock per signal per date)
signal_values(id, stock_id, signal_name, value, percentile, date, created_at)

-- Agent outputs
agent_outputs(id, run_id, stock_id, agent_name, score, rationale, flags jsonb, raw_response text, created_at)

-- Regime tracking
regime_states(id, detected_at, regime_id, confidence, vix, yield_spread, hml_spread, pmi, macro_snapshot jsonb)

-- Validation / paper trading
paper_trade_results(id, pick_id, start_date, end_date, start_price, end_price, return_pct, benchmark_return_pct, alpha, status)
brier_scores(id, quarter, agent_name, brier_score, skill_score, weight, created_at)

-- User management
user_entitlements(id, clerk_user_id, stripe_customer_id, tier, market_access text[], api_calls_remaining, api_calls_reset_at, created_at, updated_at)
chat_messages(id, user_id, role, content, ticker_context, tokens_used, created_at)
alerts(id, user_id, stock_id, condition jsonb, is_active, last_triggered_at, created_at)
```

### 6.4 Failure Modes & Recovery

| Failure | Detection | Recovery Strategy |
|---------|-----------|------------------|
| Data source down (yfinance, NSE API) | DataBroker health check before pipeline run | Use last cached values + flag data as "stale"; degrade gracefully, do not abort run |
| Claude API timeout (agent call) | 30s timeout + asyncio timeout wrapper | Retry up to 3× with exponential backoff (5s, 15s, 45s). If all fail: mark agent as "UNAVAILABLE", reduce conviction tier by one level for affected stocks |
| Claude API rate limit (429) | Response status code | Pause affected agent batch 60s, retry; if persists, queue remaining batches for next slot |
| Celery task failure | DLQ + Sentry alert | Dead-letter queue captures failed tasks; ops alert to Slack/email; manual re-trigger via admin API |
| Quarterly run failure at Phase 3+ | Run status = "PARTIAL" | Resume from last completed phase (idempotent phase IDs stored in quarterly_runs.metadata) |
| User-facing API error | Standard HTTP error codes | Return structured error: `{error: string, code: string, retry_after?: number}`; never expose internal state |
| Claude API cost spike | Monthly budget monitor | Per-user token budget enforced in middleware; if monthly budget exceeded, downgrade chat to claude-haiku; circuit breaker alerts at 80% of monthly budget cap |

---

## 7. Product & User Flows (Layer 5)

### 7.1 Five Core Screens

1. **Dashboard** — Current regime badge, Top 3 picks (free tier teaser), 4-quarter track record, market pulse (VIX/yields/FII flows), AI chat widget
2. **Quarterly Picks** — Full ranked list (Top 15), filter by market/sector/conviction, per-stock thesis cards, expand → full 7-agent dossier, portfolio blueprint builder
3. **Stock Deep Dive** — TradingView chart, per-agent scorecards, ADVERSARIAL bear case (prominent), 10-signal breakdown, insider activity timeline, earnings surprise history
4. **Validation Center** — Live accuracy vs S&P 500 + Nifty 50, quarter-by-quarter track record, per-agent accuracy, regime-stratified performance, Wall Street comparison
5. **AI Research Chat** — Conversational interface to wall-street-analyst skill suite (DCF, Goldman Screener, Bridgewater Risk, etc.), share analysis links (viral growth)

### 7.2 Key UX Principle: Explain Everything
Every score has a "why." Every pick shows agent agreement count. The ADVERSARIAL bear case is always visible. No competitor does this — it becomes a trust moat over time.

---

## 8. Monetization

### 8.1 Pricing Tiers

| Tier | Price | Key Features |
|------|-------|-------------|
| Free | $0 | Top 3 picks preview, 3 deep-dives/day, 5 AI chat messages/day, track record public |
| Pro Global | $29/mo ($19/mo annual) | All 15 picks, full agent dossiers, portfolio builder, unlimited chat, API 1K calls/mo, CSV/PDF export |
| Pro India | ₹499/mo (₹3,999/year) | India-focused, IPO analysis, F&O support, promoter alerts, FII tracker, SEBI-compliant |
| Enterprise | Custom | Brokerage white-label, unlimited API, custom agent tuning, SLA, data licensing |

### 8.2 Revenue Projections

| Stream | Year 1 ARR | Year 2 ARR | Year 3 ARR | Margin |
|--------|-----------|-----------|-----------|--------|
| Pro subscriptions (Global + India) | $50K | $250K | $500K | 85% |
| Enterprise/white-label | $30K | $180K | $400K | 90% |
| API access | $10K | $60K | $150K | 80% |
| Research reports | $15K | $40K | $80K | 70% |
| Affiliate + data licensing | $5K | $20K | $125K | 95% |
| **Total** | **~$110K** | **~$550K** | **~$1.25M** | **~85%** |

**India Pro revenue note:** ₹499/mo ≈ $5.94 USD at ~₹84/USD. India Pro subscribers tracked separately. Year 1 assumption: 500 India Pro + 120 Global Pro subscribers for the $50K blended ARR figure.

### 8.3 Unit Economics
- Pro Global LTV formula: `p / c` where p = $29/mo, c = monthly churn rate
  - Conservative (7% monthly churn, 84% annual): LTV = $29 / 0.07 = ~$414
  - Base case (4% monthly churn, 40% annual): LTV = $29 / 0.04 = ~$725
  - Annual plan (≈2% monthly churn): LTV = $19 / 0.02 = ~$950
  - Note: 7% churn is high for a sticky financial tool; 4% is the base case assumption
- CAC target: <$40 (3-4 month payback on monthly, <2 month on annual)
- India brokerage white-label: ₹3-5L/month per partner (~$3.5-6K/mo)

---

## 9. Validation Engine (Layer 4)

### 9.1 Three-Mode Validation
1. **Backtest** — Run system on 16+ historical quarters (2022–2025). Measure: IC, ICIR, hit rate vs benchmark, Sharpe ratio, regime-stratified performance. Walk-forward: Train 5Y, Validate 1Y, Test 6-month OOS, retrain quarterly.
2. **Paper Trading** — Every quarterly pick is published with timestamp. After 90 days, system auto-scores vs S&P 500 (US picks), Nifty 50 (India picks), MSCI World (global). Accuracy leaderboard is **public** — trust through transparency.
3. **Wall Street Cross-Check** — Compare picks vs Goldman Sachs consensus targets, Morgan Stanley analyst ratings, Refinitiv/FactSet aggregates. Show where NeuralQuant agrees or diverges from Wall Street consensus.

### 9.2 Validation Metrics (Non-Negotiable)
- Always report IC + ICIR + hit rate + turnover-adjusted IC
- Apply transaction cost model: 5bps large-cap, 15bps mid-cap, 30bps small-cap
- Report performance per regime (a signal should add value in ≥3/4 regimes)
- Brier Score per confidence tier — auto-tighten thresholds if targets missed

---

## 10. Go-To-Market Strategy

### 10.1 Positioning
**"AI-powered investment research — understand any stock in 60 seconds."**
Not "AI stock tips" — regulatory risk (SEBI), trust deficit, and commoditization. The value is analysis and transparency, not prediction.

### 10.2 India-First Beachhead
- 60M+ active retail investors in India (185M+ DEMAT accounts as of March 2025)
- Pain points: information asymmetry, dangerous tip culture, earnings surprise prediction, IPO overload, F&O decision support, small-cap discovery
- Willingness to pay: ₹499–999/mo for trusted tools (Zerodha Prime/Tickertape Pro benchmarks)
- Distribution: Zerodha Varsity, TradingView India community, YouTube finance creators (100K–300K subscribers), programmatic SEO (NeuralQuant analysis page per NSE 500 stock)

### 10.3 GTM Phases
| Phase | Timeline | Target | Key Actions |
|-------|----------|--------|-------------|
| Pre-launch | Weeks 1–4 | 300–500 waitlist | Build in public on X, GitHub repo live, open-source components |
| Launch | Weeks 5–6 | 500–1,500 signups | ProductHunt, Hacker News "Show HN", Reddit finance communities |
| Community | Months 2–3 | 1,000+ users | TradingView indicators, YouTube creator partnerships, Zerodha Varsity |
| Enterprise | Months 4–8 | First brokerage deal | Angel One/5paisa pilot, 90-day at 50% discount |

### 10.4 Competitive Moat
1. **India data depth** — best NSE/BSE fundamental + sentiment pipeline; no US competitor has this
2. **Explainability** — Claude's reasoning is a genuine differentiator; every score has a "why"
3. **Track record transparency** — logged predictions, public accuracy; builds trust over 12+ months
4. **Open-core GitHub presence** — community flywheel, developer mindshare, brokerage discovery

---

## 11. GitHub Repository Strategy

### 11.1 Open-Core Model
**Public (open-source, Apache 2.0):**
- `packages/signals/` — 10-factor signal library
- `packages/data/` — all 20+ data source connectors
- `packages/ml/` — LightGBM ranker framework + FinBERT pipeline
- Regime detection engine
- Python SDK for the NeuralQuant API
- Architecture docs + design specs

**Proprietary (cloud-only):**
- `packages/agents/` — 7-agent system prompts and orchestration
- Head Analyst synthesis logic
- Confidence calibration + feedback loop weights
- Production signal combination layer

### 11.2 README Structure
1. Hero banner with animated dashboard GIF
2. Badges: GitHub stars, license, build status, PyPI version
3. One-line pitch + 3-bullet summary
4. Architecture diagram (7-agent system)
5. Live track record table (backtested quarters vs benchmark)
6. Quick start — 5 commands to run locally
7. Data pipeline overview
8. Open-core model explanation
9. Contributing guide
10. Public roadmap with milestones
11. SEBI + financial disclaimer

---

## 12. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SEBI non-compliance (India) | High if unaddressed | Existential | Register as RA before India launch; label all outputs as "research" not "advice" |
| US Investment Adviser Act violation | Medium if unaddressed | High | Position as "impersonal research tool"; sizing guidance labeled "illustrative not personalized"; legal review before US public launch; explicit SEC-compliant disclaimers |
| Claude API cost spike at scale | Medium | High | Per-user token budget enforced in middleware; monthly budget circuit breaker (alert at 80%, downgrade at 100%); cache repeated queries; claude-haiku as fallback for non-critical paths. Estimate: ~$15-50 per quarterly run; ~$0.05-0.20 per on-demand deep-dive |
| NSE unofficial API breaking | Medium | High | Bhavcopy bulk download as fallback; jugaad-data library handles headers; 0.5-1s delay between requests |
| LLM hallucination of financial data | Medium | High | Agents only cite provided context — never recall financial figures from training; output validation layer checks all numbers against source data |
| Market downturn churn | High (cyclical) | Medium | Counter-cyclical features: portfolio risk analysis, hedging suggestions, bear-market picks; annual plan incentives |
| Black swan / regime break | Low | High | Regime Uncertainty Flag: all picks auto-downgrade to SPECULATIVE when macro confidence <60% |
| V8 logic overfitting to India/historical data | Medium | Medium | Walk-forward validation, out-of-sample testing on US data from day 1 |
| Screener.in scraping ToS violation | Medium | Medium | Fallback: BSE XBRL filings (free, official); negotiate data partnership once revenue supports it; Trendlyne API as paid alternative |
| Open-source signals → competitive copying | Medium | Low-Medium | Open-source signal framework + connectors only; factor weights, combination logic, and IC-ranked ordering stay proprietary in cloud layer |
| Earnings transcript source fragility | Medium | Medium | Seeking Alpha 24-48hr delay acceptable for quarterly analysis; IR website scraping as fallback; budget for paid transcripts at $500-2K/mo once revenue allows |
| Data vendor dependency | Low | Medium | Diversify across 20+ sources; no single point of failure; Polygon.io as paid upgrade path |

---

## 13. Implementation Phases

### Phase 1 — Foundation (Weeks 1–6)
- Monorepo setup (Turborepo, TypeScript + Python)
- Core data pipeline: yfinance + NSE Bhavcopy + FRED + EDGAR XBRL
- LightGBM signal engine + 10-factor library (evolved from V8)
- Regime HMM detector
- Backtesting framework (16+ quarters)

### Phase 2 — Agent System (Weeks 7–9)
- 7-agent Claude architecture with PARA-DEBATE protocol
- Agent prompts + context packaging
- QUANT-RANK aggregation + HEAD ANALYST synthesis
- Confidence scoring + Brier calibration framework

### Phase 3 — Product (Weeks 10–13)
- Next.js 15 frontend (5 screens, Stitch UI generation)
- FastAPI backend + Supabase integration
- Clerk auth + Stripe billing
- Paper trading tracker

### Phase 4 — Validation & Launch (Weeks 14–16)
- Full backtest pipeline (2022–2025 quarters)
- Validation Center (accuracy leaderboard)
- GitHub repo + README
- ProductHunt + HN launch prep

### Phase 5 — Growth (Months 4–6)
- India Pro tier (₹499/mo, SEBI-compliant)
- AI Research Chat (wall-street-analyst skill integration)
- Enterprise pilot (first brokerage)
- Programmatic SEO (NSE 500 analysis pages)

---

## 14. Success Criteria

| Milestone | Target | Timeline |
|-----------|--------|----------|
| GitHub stars | 500+ | Month 1 |
| Free users | 1,000+ | Month 2 |
| Pro subscribers | 100+ | Month 3 |
| Backtest win rate (HIGH tier) | >65% vs benchmark | Before launch |
| First enterprise deal | 1 brokerage signed | Month 6 |
| ARR | $50K+ | Month 6 |
| ARR | $110K+ | Month 12 |
| ARR | $500K+ | Month 24 |

---

*This document is the approved design specification for NeuralQuant. Implementation begins with the writing-plans skill to break this spec into a detailed, week-by-week build plan.*

> **Disclaimer:** NeuralQuant outputs are AI-generated research for informational purposes only. They do not constitute investment advice. Past performance does not guarantee future results. Always consult a licensed financial advisor before making investment decisions.
