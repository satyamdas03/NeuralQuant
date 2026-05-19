# Automated Trading & Risk Engine — Implementation Plan

Date: 2026-05-13 | Branch: master | Base: master

## Summary

Add automated trading signals with risk management discipline to NeuralQuant. New standalone feature: `/trade` route with its own page, sidebar entry, backend router, and signal engine extensions. Zero modifications to existing critical paths (stocks, analyst, query, dashboard, backtest). Borrows risk patterns from polymarket-pipeline (edge detection, Kelly sizing, calibration tracking) and social patterns from AI-Trader (signal feed, strategy presets).

---

## Architecture Decision: Separate Feature, Separate Code Paths

New feature lives entirely in new files. Existing modules are imported but never modified:

```
New files (7-9 files, zero existing-file changes except SideNavBar.tsx NAV array):
├── apps/api/src/nq_api/routes/trade.py          # NEW: /trade/* endpoints
├── apps/web/src/app/trade/page.tsx              # NEW: Trade page
├── apps/web/src/components/trade/                # NEW: trade-specific components
│   ├── SignalFeed.tsx                            # live signal feed
│   ├── StrategyCard.tsx                          # strategy preset card
│   ├── RiskDashboard.tsx                         # drawdown/concentration widgets
│   ├── PositionSizer.tsx                         # Kelly calculator UI
│   └── CalibrationPanel.tsx                      # accuracy-over-time chart
├── packages/signals/src/nq_signals/risk.py       # NEW: risk management module
└── packages/signals/src/nq_signals/calibration.py # NEW: calibration tracker

Existing files touched (minimal — only to register new items):
└── apps/web/src/components/layout/SideNavBar.tsx  # +1 NAV entry
└── apps/web/src/components/layout/BottomMobileNav.tsx  # +1 NAV entry (optional)
```

---

## Phase 1: Risk Management Engine (packages/signals)

### 1a. Risk Module (`packages/signals/src/nq_signals/risk.py`)

New module. No imports from existing nq_signals modules (avoids circular deps). Pure computation functions:

```python
# Functions to implement:

def compute_edge(composite_score: float, threshold: float = 70.0) -> float:
    """Normalize composite_score (0-100) to edge (0-1).
    Only scores above threshold produce positive edge.
    edge = max(0, (composite_score - threshold) / (100 - threshold))"""
    pass

def size_position_kelly(
    edge: float,
    bankroll: float,
    win_probability: float = 0.55,
    kelly_fraction: float = 0.25
) -> float:
    """Quarter-Kelly position sizing.
    bet = bankroll * edge * kelly_fraction
    Capped at user-defined max_bet and floored at $1.00."""
    pass

def compute_daily_drawdown(
    pnl_history: list[float],
    daily_loss_limit: float = 100.0
) -> dict:
    """Returns {current_drawdown, limit_breached, remaining_budget}"""
    pass

def compute_concentration_risk(
    positions: dict[str, float],  # {ticker: dollar_value}
    total_portfolio: float,
    max_single_position_pct: float = 0.20
) -> dict:
    """Returns {overconcentrated_tickers, concentration_score, warning_level}"""
    pass
```

### 1b. Calibration Tracker (`packages/signals/src/nq_signals/calibration.py`)

Tracks signal accuracy over time. Logs to Supabase (new table or reuse score_cache_history):

```python
@dataclass
class SignalRecord:
    ticker: str
    signal_date: str          # when signal was generated
    composite_score: float
    edge: float
    direction: str            # "bullish" | "bearish"
    entry_price: float
    exit_price: float | None  # None until closed/resolved
    pnl: float | None
    resolved: bool
    resolution_date: str | None

class CalibrationTracker:
    def log_signal(self, record: SignalRecord) -> None: ...
    def resolve_signal(self, signal_id: str, exit_price: float, pnl: float) -> None: ...
    def get_accuracy(self, lookback_days: int = 90) -> dict:
        """Returns {hit_rate, avg_pnl, sharpe, profit_factor, n_trades}"""
    def get_by_ticker(self, ticker: str) -> list[SignalRecord]: ...
```

### 1c. Integration with SignalEngine (read-only, no modifications)

The risk module is called AFTER `engine.compute()` returns results. Flow:

```
engine.compute(snapshot) → DataFrame
    ↓
risk.compute_edge(df['composite_score']) → add edge column
    ↓
risk.size_position_kelly(edge, bankroll) → add position_size column  
    ↓
Return enriched DataFrame to trade route
```

This ensures zero modification to `engine.py` — risk is a post-processing layer.

---

## Phase 2: Trade API Router (`apps/api/src/nq_api/routes/trade.py`)

New FastAPI router at `/trade`:

### Endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| `GET` | `/trade/signals` | Signal feed — top stocks with edge + position size | Optional |
| `GET` | `/trade/strategies` | Strategy presets list (momentum_breakout, value_play, etc.) | Public |
| `GET` | `/trade/strategies/{preset_id}` | Signals filtered by preset | Optional |
| `GET` | `/trade/calibration` | Signal accuracy report | Optional |
| `GET` | `/trade/risk-profile` | User's risk settings (from UserProfile) | Auth |
| `POST` | `/trade/risk-profile` | Update risk settings | Auth |
| `GET` | `/trade/positions` | Paper trading positions (from calibration tracker) | Auth |

### Signal Feed Response:

```python
class TradeSignal(BaseModel):
    ticker: str
    market: Market
    composite_score: float
    score_1_10: float
    regime_label: str
    verdict: str               # from PARA-DEBATE cache
    edge: float                # 0-1, >0 = actionable
    position_size: float       # Kelly-derived $ amount
    direction: str             # "bullish" | "bearish"
    sub_scores: dict
    last_updated: str
```

### Guardrails in the router:

1. Edge threshold configurable via env `TRADE_EDGE_THRESHOLD` (default 0.10)
2. Min score configurable via env `TRADE_MIN_SCORE` (default 70.0)
3. Max signals per request capped at 20
4. All values explicitly marked [PAPER TRADING ONLY]
5. No real execution — signals only. Broker integration is Phase 3.

---

## Phase 3: Frontend (`apps/web/src/app/trade/page.tsx`)

### Page Layout (3-panel desktop, stacked mobile):

```
┌──────────────────────────────────────────────────────────┐
│  Top Bar: Regime Badge | Market Toggle (US/IN) | Refresh  │
├──────────────────────┬───────────────────────────────────┤
│                      │                                   │
│   SIGNAL FEED        │   RISK DASHBOARD                  │
│   (left, 60%)        │   (right, 40%)                    │
│                      │                                   │
│   TradeSignal cards  │   - Daily drawdown gauge          │
│   sorted by edge     │   - Concentration chart           │
│   with:              │   - Calibration hit rate          │
│   - ticker + score   │   - Kelly calculator              │
│   - edge bar         │   - Strategy presets              │
│   - position size    │                                   │
│   - direction badge  │   CALIBRATION PANEL               │
│   - expand for PARA  │   (bottom right)                  │
│                      │   - accuracy over time chart      │
│                      │   - by-preset breakdown           │
├──────────────────────┴───────────────────────────────────┤
│  STRATEGY PRESETS ROW (horizontal chips, scrollable)     │
│  [Momentum Breakout] [Value Play] [Quality Compound] ... │
└──────────────────────────────────────────────────────────┘
```

### Components:

1. **`SignalFeed.tsx`** — scrollable list of `TradeSignal` cards. Each card shows:
   - Ticker, company name, market badge
   - composite_score → edge bar (gradient: gray→green)
   - Kelly position size (with bankroll input at top)
   - Direction badge (🟢 Bullish / 🔴 Bearish)
   - Expand → shows sub_scores mini-radar

2. **`RiskDashboard.tsx`** — key metrics widgets:
   - Drawdown gauge (semicircle chart, green/yellow/red zones)
   - Concentration donut chart (by ticker)
   - Daily loss limit status (progress bar: $X / $100 used)

3. **`StrategyCard.tsx`** — preset chip with icon + label + brief description. Click filters signal feed.

4. **`CalibrationPanel.tsx`** — accuracy metrics:
   - Hit rate % (big number)
   - Avg PnL per trade
   - Profit factor
   - N trades in lookback window
   - Mini sparkline of cumulative PnL

5. **`PositionSizer.tsx`** — interactive Kelly calculator:
   - Bankroll input
   - Edge slider
   - Win probability slider
   - Output: recommended bet size

### Sidebar Registration:

Add to `SideNavBar.tsx` NAV array (line 21-33):
```tsx
{ href: "/trade", label: "Trade", icon: TrendingUp },
```

Add to `BottomMobileNav.tsx` NAV array (optional — 6 items already, can swap if needed).

Import `TrendingUp` from lucide-react in SideNavBar.tsx.

---

## Phase 4: Supabase (new table)

### `signal_log` table:

```sql
CREATE TABLE IF NOT EXISTS signal_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    guest_id TEXT,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    signal_date DATE NOT NULL,
    composite_score FLOAT,
    edge FLOAT,
    direction TEXT,
    position_size FLOAT,
    entry_price FLOAT,
    exit_price FLOAT,
    pnl FLOAT,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_date DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_signal_log_user ON signal_log(user_id, signal_date);
CREATE INDEX idx_signal_log_ticker ON signal_log(ticker, signal_date);
```

---

## What NOT in Scope (deferred)

| Item | Reason |
|------|--------|
| Real broker execution (Alpaca/Zerodha) | Phase 3 — needs broker API keys, compliance review, legal disclaimer update |
| Real money trading | Regulatory minefield — needs legal before any code |
| AI-Trader-style copy trading (follow other users) | Needs user graph, follower system — 10+ new tables, auth overhaul |
| Polymarket integration | No user demand signal yet |
| Mobile trade execution UI | Current mobile nav has 6 slots all filled — redesign needed |
| Automated order placement from signals | Even paper — UX flow needs confirmation dialogs, order status tracking |
| IN market Kelly sizing with INR | Currency conversion in risk engine — non-trivial, Phase 3 |

---

## What Already Exists (reuse, don't rebuild)

| Existing | How reused |
|----------|-----------|
| `SignalEngine.compute()` | Called as-is, risk layer added downstream |
| `row_to_ai_score()` | Used to build `TradeSignal` from DataFrame rows |
| `score_cache.read_top()` | Signal feed pulls from cache first, live compute fallback |
| `PRESETS` in `screener.py` | Reused — trade strategies are same 5 presets + edge filter |
| `UserProfile.risk_profile` | Drives Kelly fraction (conservative=0.15, balanced=0.25, aggressive=0.40) |
| `RegimeDetector` | Regime context displayed in trade page top bar — imported, not modified |
| `_get_live_regime_id()` | Called from trade router to show current regime |
| `AppShell` | Auto-wraps `/trade` page with sidebar + mobile nav |
| `GlassPanel`, `GradientButton`, `RegimeBadge` | Reused UI primitives for trade page components |
| Supabase `score_cache_history` | Backfills calibration data — no new ETL needed |

---

## Architecture ASCII Diagram

```
                        ┌──────────────────────┐
                        │   Existing (UNTOUCHED) │
                        │   ─────────────────── │
                        │   SignalEngine.compute()│
                        │   RegimeDetector       │
                        │   score_cache          │
                        │   row_to_ai_score()    │
                        │   FMP / yfinance       │
                        └──────────┬─────────────┘
                                   │ DataFrame (composite_score, sub_scores)
                                   │ READ-ONLY — no existing code modified
                                   ▼
        ┌──────────────────────────────────────────────────┐
        │              NEW: risk.py                        │
        │  ┌────────────┐  ┌──────────────┐  ┌──────────┐ │
        │  │compute_edge │  │size_position │  │drawdown  │ │
        │  │(score→0-1) │  │_kelly(bankroll│  │_check()  │ │
        │  │             │  │  , edge, 0.25)│  │          │ │
        │  └────────────┘  └──────────────┘  └──────────┘ │
        └──────────────────────┬───────────────────────────┘
                               │ Enriched DataFrame (+edge, +position_size)
                               ▼
        ┌──────────────────────────────────────────────────┐
        │              NEW: trade.py (FastAPI router)      │
        │  GET /trade/signals     → TradeSignal[]          │
        │  GET /trade/strategies  → Preset[]               │
        │  GET /trade/calibration → CalibrationReport      │
        │  POST /trade/risk-profile                         │
        └──────────────────────┬───────────────────────────┘
                               │ JSON
                               ▼
        ┌──────────────────────────────────────────────────┐
        │              NEW: /trade page                    │
        │  ┌──────────┐ ┌──────────────┐ ┌──────────────┐ │
        │  │SignalFeed│ │RiskDashboard │ │Calibration   │ │
        │  │(cards)   │ │(drawdown,    │ │Panel(hit     │ │
        │  │          │ │concentration)│ │rate, PnL)    │ │
        │  └──────────┘ └──────────────┘ └──────────────┘ │
        └──────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────┐
        │              NEW: calibration.py                 │
        │  CalibrationTracker → Supabase signal_log        │
        │  Tracks: hit_rate, avg_pnl, sharpe, profit_factor│
        └──────────────────────────────────────────────────┘
```

---

## Test Plan

### Backend (pytest):

1. **`test_risk.py`** — unit tests for risk module (no API/DB deps):
   - `test_compute_edge_score_90` → assert edge ≈ 0.67
   - `test_compute_edge_below_threshold` → assert edge == 0.0
   - `test_kelly_bankroll_10000_edge_0_1` → assert bet == 250.0
   - `test_kelly_capped_at_max_bet` → assert bet ≤ MAX_BET
   - `test_daily_drawdown_limit_breached` → assert limit_breached == True
   - `test_concentration_over_20pct` → assert warning_level == "HIGH"

2. **`test_trade_router.py`** — integration tests for /trade endpoints:
   - `test_get_signals_returns_array` → assert len > 0
   - `test_get_signals_respects_max` → assert len ≤ 20
   - `test_get_strategies_returns_5_presets`
   - `test_get_calibration_empty_state` → returns zeros, not 500

### Frontend (manual QA checklist):

- [ ] `/trade` page loads without error
- [ ] Signal feed renders cards with scores, edges, position sizes
- [ ] Strategy chips filter the feed
- [ ] US/IN toggle switches market and refreshes data
- [ ] Risk dashboard shows drawdown gauge
- [ ] Calibration panel shows hit rate
- [ ] Sidebar "Trade" item highlights when active
- [ ] Mobile responsive: stacked layout, nav shows Trade
- [ ] No 500/503 on any existing page (dashboard, stocks, screener, terminal)
- [ ] No regression on existing endpoints (health check, market/movers, stocks/meta)

### Existing endpoints that MUST still work (verified before merge):

```
GET /health
GET /market/movers
GET /stocks/AAPL
GET /stocks/AAPL/meta?market=US
GET /stocks/TCS/meta?market=IN
GET /screener/preview
POST /screener
GET /backtest/accuracy
POST /terminal/query
POST /query/v2/stream
```

---

## Failure Modes & Rescue

| Failure | Impact | Rescue |
|---------|--------|--------|
| risk.py import fails (missing dep) | `/trade` 500, all other routes unaffected (separate router) | Disable trade router in main.py via env `TRADE_ENABLED=false` |
| Supabase signal_log table not created | POST calibration fails, GET returns empty array | Catch in router → return empty `[]` with warning log, degrade gracefully |
| SideNavBar.tsx NAV array syntax error | Entire frontend fails to compile | Add entry last, test with `npx next build` before pushing |
| Kelly calculation divide-by-zero (bankroll=0) | `/trade/signals` 500 | Input validation: bankroll must be > 0, return error message not crash |
| Existing score_cache corrupted | Both /trade AND /screener affected | Not a trade-specific risk — existing cache has tiered fallback |
| yfinance 401 on Render (known issue) | Live compute fails, stale cache serves | Trade route uses cache-first (same as screener), live compute disabled on Render |

---

## Error & Rescue Registry

| Error Path | User Sees | System Does |
|-----------|-----------|------------|
| No signals above edge threshold | "No actionable signals right now. Try lowering threshold in settings." | Return 200 with empty array + message |
| Bankroll not set | Kelly calculator shows "--" | Return edge only, position_size = null |
| Supabase unreachable | Calibration shows "Data temporarily unavailable" | Return cached values if < 24h old, zeros otherwise |
| Invalid preset_id | 400: "Unknown strategy preset" | Validate against PRESETS list |
| Missing risk_profile | Default to "balanced" (kelly_fraction=0.25) | Don't error — sensible default |

---

## Implementation Sequence

### Day 1: Risk Engine + API (backend only)

1. Create `packages/signals/src/nq_signals/risk.py` — pure functions
2. Create `packages/signals/src/nq_signals/calibration.py` — CalibrationTracker
3. Create `apps/api/src/nq_api/routes/trade.py` — all endpoints
4. Register trade router in `main.py` (line ~120, where routers are added)
5. Run `pytest packages/signals/tests/` — verify risk unit tests
6. Test locally: `curl http://localhost:10000/trade/signals?market=US`

### Day 2: Frontend + Sidebar

1. Create `apps/web/src/app/trade/page.tsx` — main page
2. Create `apps/web/src/components/trade/SignalFeed.tsx`
3. Create `apps/web/src/components/trade/RiskDashboard.tsx`
4. Create `apps/web/src/components/trade/CalibrationPanel.tsx`
5. Add NAV entry to `SideNavBar.tsx`
6. Run `npx next build` — verify no compilation errors
7. Test locally on `http://localhost:3000/trade`

### Day 3: Integration Testing + Deploy

1. Full end-to-end test: all trade endpoints + UI
2. Verify all existing endpoints still work (regression test list above)
3. Push to master → trigger Render + Vercel deploy
4. Verify production: `https://neuralquant.co/trade`

---

## Decisions Log

| # | Decision | Principle | Rationale |
|---|----------|-----------|-----------|
| 1 | New files only, no existing file modifications (except SideNavBar.tsx) | P3 pragmatic | Prevents regression on 19 existing routes. Blast radius zero. |
| 2 | Risk as post-processing, not inside engine.compute() | P5 explicit | engine.compute() is 174 lines of tested logic. Injecting risk there risks breaking screener/backtest. |
| 3 | Quarter-Kelly default (not half or full) | P1 completeness | Polymarket-pipeline uses quarter-Kelly. Conservative, proven, ruins risk low. |
| 4 | Cache-first for signal feed (not live compute) | P3 pragmatic | Same pattern as screener/preview. Live compute kills Render (yfinance rate limits). |
| 5 | Separate `/trade` route, not embedded in `/screener` | User requirement | User explicitly: "separate page, separate feature, sidebar button." |
| 6 | signal_log new table, not reusing score_cache_history | P5 explicit | Different schema (PNL, exit_price, resolution) — forcing into score_cache_history would be fragile. |
| 7 | No mobile nav change (keep 6 items) | P3 pragmatic | Mobile nav has 6 slots, all used. Adding 7th crowds UI. Add only to desktop sidebar for now. |

---

## GSTACK REVIEW REPORT

| Phase | Skill | Status | Findings |
|-------|-------|--------|----------|
| CEO | plan-ceo-review | RAN (auto) | Premises confirmed reasonable. Scope: Phase 1+2 now, Phase 3 deferred. Market risk: automated trading claims need legal disclaimer. |
| Design | plan-design-review | SKIPPED | No UI scope in plan — using existing design system (Obsidian Quantum). New components follow existing patterns. |
| Eng | plan-eng-review | RAN (auto) | Architecture sound. Risk module independent of engine (no circular deps). signal_log table clean. Edge cases covered: empty signals, zero bankroll, missing risk_profile. |
| DX | plan-devex-review | SKIPPED | No developer-facing scope — this is internal feature work, not SDK/API product. |

Verdict: **APPROVED for implementation.** No blocking issues. 3 taste decisions surfaced at gate.
