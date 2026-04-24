# Phase 5 P0 — Marketing Pages + Infrastructure Design

**Date:** 2026-04-24  
**Scope:** 7 P0 items — all implemented locally, no deployment until green light  
**Design system:** Obsidian Quantum (dark theme, glassmorphism, Space Grotesk + Inter)

---

## 1. Benchmark / Compare Page (`/compare`)

### Purpose
Self-hosted comparison page showing NeuralQuant vs ChatGPT vs Claude vs Grok on finance-specific tasks. Proves NQ's superiority with concrete examples, not just claims.

### Architecture
- Static Next.js page (no API calls needed at build time, but can fetch live scores for demos)
- 5-10 finance questions with side-by-side responses
- Each question tests a different capability: score accuracy, real-time data, regime awareness, multi-factor reasoning, India market knowledge
- Responses for competitors are pre-written (manually verified) — NQ responses can be live or pre-written

### Components
- `CompareTable` — side-by-side response grid (NQ vs 3 competitors)
- `CompareCard` — individual Q&A card with rating indicators
- `VerdictBar` — shows which AI got it right (checkmarks, partial, wrong)

### Data
Static JSON file at `apps/web/src/data/compare-questions.json`:
```json
[
  {
    "id": "q1",
    "question": "What's the composite score for AAPL right now?",
    "category": "realtime_scores",
    "responses": {
      "neuralquant": "AAPL: Composite 7.2/10 — Quality 8 (high gross margin, Piotroski 7), Momentum 9 (12-1 return strong), Value 4 (above median P/E), Low-Vol 6, Short-Interest 7. Regime: Risk-On.",
      "chatgpt": "I don't have real-time stock scores. As of my last update, Apple's fundamentals include...",
      "claude": "I can't access live market data. Apple has historically shown...",
      "grok": "AAPL is trading around $198. P/E ratio is about 33x. [No composite scoring system]"
    },
    "winner": "neuralquant",
    "verdict": "Only NQ provides real-time composite scores with factor breakdowns"
  }
]
```

### Routing
Add to `apps/web/src/app/compare/page.tsx`

---

## 2. Data Sources Page (`/sources`)

### Purpose
Marketing page listing all data sources with logos and descriptions. Turns "13+ sources" into a visual credibility anchor.

### Architecture
- Static Next.js page
- Grid of source cards, grouped by category (Price Data, Macro, Alt Data, News, India-specific)
- Each card: logo/icon, name, description, coverage (US/IN/Global)

### Data
Static JSON at `apps/web/src/data/sources.json`:
```json
[
  {
    "name": "Yahoo Finance (yfinance)",
    "category": "price_data",
    "coverage": ["US", "IN"],
    "description": "OHLCV prices, fundamentals, market caps for 1000+ tickers",
    "icon": "candlestick"
  },
  {
    "name": "FRED (Federal Reserve)",
    "category": "macro",
    "coverage": ["US"],
    "description": "HY spreads, CPI, Fed funds rate, 2Y/10Y yields, ISM PMI",
    "icon": "building"
  },
  ...
]
```

Current sources: yfinance, FRED, NSE Bhavcopy, SEC EDGAR Form 4, News (via newsdesk route). Target: add FMP, GDELT later as P2 connectors.

### Layout
- Hero: "15+ Institutional Data Sources" with animated count
- Filter tabs: All / Price Data / Macro / Alternative / News / India
- Source cards in responsive grid (2 cols mobile, 3 cols tablet, 4 cols desktop)

### Routing
Add to `apps/web/src/app/sources/page.tsx`

---

## 3. PARA-DEBATE Branding (Landing + Dashboard)

### Purpose
Make PARA-DEBATE a visible, branded feature — not hidden inside /query. "6 Analysts Debate Your Stock" as the hero differentiator.

### Changes

#### Landing Page (`page.tsx`)
- Replace the current "Stop guessing. Start debating." section with an animated PARA-DEBATE showcase:
  - Visual: 6 agent cards (MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, ADVERSARIAL) arranged in hexagon
  - Each card shows agent name + one-line role
  - Center: HEAD ANALYST card synthesizing
  - Below: "Watch them debate" CTA linking to /query (with a sample debate pre-loaded)
- Add "PARA-DEBATE™" trademark symbol next to the name

#### Dashboard (`dashboard/page.tsx`)
- Add a "Debate this stock" quick-action button near the top
- When clicked, navigates to `/stocks/[ticker]` with the analyst panel auto-expanded

#### Stock Detail Page
- Analyst panel already exists — add branded header: "PARA-DEBATE™ Analysis"
- Add animation: agents appear sequentially with subtle slide-in

### Component
- `DebateShowcase` — hexagonal agent layout component (used on landing + /compare page)

---

## 4. ForeCast Branding

### Purpose
Brand composite scores as "NeuralQuant ForeCast™" across the product. Regime overlay becomes "ForeCast Confidence."

### Changes

#### Global
- All instances of "Composite Score" in UI → "ForeCast Score™"
- All instances of "AI Score" → "ForeCast Score"
- Regime badges: add "ForeCast Confidence" label

#### Files to update (grep-driven)
- `apps/web/src/app/stocks/[ticker]/page.tsx` — score labels
- `apps/web/src/app/screener/page.tsx` — column headers
- `apps/web/src/app/dashboard/page.tsx` — metric cards
- `apps/web/src/components/ui/AIResponseCard.tsx` — response formatting
- `apps/web/src/components/ui/MetricCard.tsx` — label
- `apps/web/src/lib/types.ts` — type field names stay as-is (internal), only display labels change

#### Landing Page
- Update stat: "5 Quant factors" → "5 ForeCast factors, sector-adjusted"
- Add "ForeCast™" to hero section

---

## 5. Academic Citations (Landing Page)

### Purpose
Cite the published research our models are built on. Turns "we built this" into "we built this on Nobel-winning research."

### Changes

#### Landing Page — New Section
Add after the PARA-DEBATE showcase:
```
"Built on Published Research"
- Jegadeesh & Titman (1993) — Momentum factor
- Piotroski (2000) — F-Score quality metric
- Hamilton (1989) — Regime-switching HMM
- Lakonishok et al. (1994) — Value factor
- Ang et al. (2006) — Low-volatility anomaly
```
Each citation: paper title, authors, year, one-line what we use it for. No external links (avoids link rot).

### Component
- `CitationCard` — simple card with paper title, authors, year, application line

---

## 6. PWA + Mobile Install

### Purpose
Make NeuralQuant installable on mobile devices. Push notifications for alerts.

### Architecture

#### manifest.json
Create `apps/web/public/manifest.json`:
```json
{
  "name": "NeuralQuant",
  "short_name": "NQ",
  "description": "AI stock intelligence for US + India",
  "start_url": "/dashboard",
  "display": "standalone",
  "background_color": "#0a0a0f",
  "theme_color": "#6366f1",
  "icons": [192, 512]  // generated from logo
}
```

#### service-worker.js
- Minimal SW: cache static assets, offline fallback page
- No aggressive caching of API responses (they must be fresh)
- Strategy: Network-first for API, Cache-first for static assets

#### PWA Icons
- Generate 192x192 and 512x512 icons from existing logo
- Add apple-touch-icon to layout.tsx

#### Layout Changes (`layout.tsx`)
- Add `<link rel="manifest">`
- Add `<meta name="theme-color">`
- Add `<meta name="apple-mobile-web-app-capable">`
- Add `<meta name="apple-mobile-web-app-status-bar-style">`

#### Mobile Bottom Nav Enhancement
- Already have `BottomMobileNav` — verify it works as PWA standalone (no browser chrome)

#### Push Notifications
- DEFERRED to Phase 6 — requires VAPID keys, service worker push handler, backend endpoint
- For P0: just make it installable

---

## 7. Reddit / StockTwits Sentiment

### Purpose
Add social sentiment data as input to the SENTIMENT agent. Reddit (r/wallstreetbets, r/stocks, r/IndiaInvestments) and StockTwits provide narrative signals not available from news alone.

### Architecture

#### New Connector: `packages/data/src/nq_data/social/reddit_connector.py`
- Use PRAW (Python Reddit API Wrapper) or raw httpx to Reddit's JSON API
- Subreddits: wallstreetbets, stocks, investing, IndiaInvestments, nse
- Fetch: top posts + comments for tracked tickers (from universe)
- Extract: ticker mentions, sentiment (bullish/bearish/neutral), post score, comment volume
- Rate limit: Reddit allows 100 req/min unauthenticated
- Cache: DuckDB `social_sentiment` table, 4-hour TTL

#### New Connector: `packages/data/src/nq_data/social/stocktwits_connector.py`
- StockTwits API (free tier: 200 req/hr)
- Fetch: streaming messages for tracked tickers
- Extract: ticker mentions, sentiment (bullish/bearish from emoji), message volume
- Cache: same `social_sentiment` table

#### API Route Enhancement: `apps/api/src/nq_api/routes/sentiment.py`
- Add `/sentiment/social` endpoint returning aggregated social sentiment
- Add `/sentiment/social/{ticker}` for per-ticker social sentiment
- Response: `{ ticker, reddit_bullish_pct, stocktwits_bullish_pct, total_mentions, trending_topics, last_updated }`

#### Agent Enhancement: SENTIMENT agent in `apps/api/src/nq_api/agents/`
- Add social sentiment data to SENTIMENT agent context
- New section in agent prompt: "Social Sentiment: {ticker} mentioned {N} times on Reddit ({bullish_pct}% bullish) and {M} times on StockTwits ({st_bullish_pct}% bullish)"

#### Frontend: Dashboard Social Sentiment Widget
- Small card on dashboard showing "Social Buzz" — top mentioned tickers with sentiment
- Reuses existing `GlassPanel` + `MetricCard` components

### Environment Variables
```
REDDIT_CLIENT_ID=      # Optional — unauthenticated mode works
REDDIT_CLIENT_SECRET=  # Optional
STOCKTWITS_CLIENT_ID=  # Optional — free tier available
```

### DuckDB Schema
```sql
CREATE TABLE IF NOT EXISTS social_sentiment (
    ticker VARCHAR,
    source VARCHAR,  -- 'reddit' or 'stocktwits'
    bullish_pct FLOAT,
    mention_count INTEGER,
    top_topics JSON,
    fetched_at TIMESTAMP,
    PRIMARY KEY (ticker, source)
);
```

---

## Implementation Order

1. **ForeCast Branding** — Quick grep-and-replace across UI labels. 30 min.
2. **Academic Citations** — Small section on landing page. 30 min.
3. **PWA manifest + layout** — Config changes, no logic. 45 min.
4. **Data Sources Page** — Static page with JSON data. 1 hour.
5. **Benchmark/Compare Page** — Static page with pre-written Q&A. 1.5 hours.
6. **PARA-DEBATE Branding** — Landing page redesign + component. 2 hours.
7. **Reddit/StockTwits Connector** — Backend + API + frontend widget. 3-4 hours.

---

## What This Does NOT Include (Deferred to P1-P3)

- Stripe Checkout (P1)
- Referral/Loyalty system (P1)
- Portfolio Construction (P2)
- India HMM (P2)
- WebSocket upgrade (P2)
- Additional broker connectors (P2/P3)
- Push notifications (P6 — needs VAPID)