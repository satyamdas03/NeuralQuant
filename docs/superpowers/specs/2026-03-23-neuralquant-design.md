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
The most important architectural decision: include an **ADVERSARIAL agent** that bears the bull case on every top pick. This prevents the system from herding into consensus (the dominant failure mode of analyst teams), builds user trust through transparency, and is completely absent from every competitor.

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

### 3.4 Monorepo Structure
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
| 7 | Earnings Call NLP Tone Delta (FinBERT) | 0.03–0.05 | EDGAR transcripts (free) | Near-zero correlation with price factors → pure additive alpha |
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
Score = (FUND×0.30) + (TECH×0.20) + (SENTIMENT×0.15) + (MACRO×0.25)
      + GEO_REG_penalty (-5/-15/-40 for Med/High/Critical)
      + ADVERSARIAL_haircut (0/-10/-50 for Resolved/Unresolved/BrokenThesis)
      + CROWDING_penalty (-8 if in top-10 most common HF holdings)
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

| Stream | Year 1 ARR | Year 3 ARR | Margin |
|--------|-----------|-----------|--------|
| Pro subscriptions | $50K | $500K | 85% |
| Enterprise/white-label | $30K | $400K | 90% |
| API access | $10K | $150K | 80% |
| Research reports | $15K | $80K | 70% |
| Affiliate + data licensing | $5K | $125K | 95% |
| **Total** | **~$110K** | **~$1.25M** | **~85%** |

### 8.3 Unit Economics
- Pro Global LTV (7% monthly churn): ~$406 · Annual plan LTV: ~$600+
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
| Claude API cost at scale | Medium | High | Cache repeated stock queries; optimize prompt token efficiency; batch processing |
| NSE unofficial API breaking | Medium | High | Bhavcopy bulk download as fallback; jugaad-data library handles headers |
| LLM hallucination of financial data | Medium | High | Agents only cite provided context — never recall financial figures from training |
| Market downturn churn | High (cyclical) | Medium | Counter-cyclical features: portfolio risk analysis, hedging suggestions, bear-market picks |
| Black swan / regime break | Low | High | Regime Uncertainty Flag: all picks auto-downgrade to SPECULATIVE when confidence <60% |
| V8 logic overfitting to India/historical data | Medium | Medium | Walk-forward validation, out-of-sample testing on US data from day 1 |
| Data vendor dependency | Low | Medium | Diversify across 20+ sources; no single point of failure; Polygon.io as paid upgrade path |

---

## 13. Implementation Phases

### Phase 1 — Foundation (Weeks 1–3)
- Monorepo setup (Turborepo, TypeScript + Python)
- Core data pipeline: yfinance + NSE Bhavcopy + FRED + EDGAR XBRL
- LightGBM signal engine + 10-factor library (evolved from V8)
- Regime HMM detector
- Backtesting framework (16+ quarters)

### Phase 2 — Agent System (Weeks 4–6)
- 7-agent Claude architecture with PARA-DEBATE protocol
- Agent prompts + context packaging
- QUANT-RANK aggregation + HEAD ANALYST synthesis
- Confidence scoring + Brier calibration framework

### Phase 3 — Product (Weeks 7–9)
- Next.js 15 frontend (5 screens, Stitch UI generation)
- FastAPI backend + Supabase integration
- Clerk auth + Stripe billing
- Paper trading tracker

### Phase 4 — Validation & Launch (Weeks 10–12)
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
