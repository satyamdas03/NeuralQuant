# Pillar D Implementation Plan — Backtesting (backtrader)

> superpowers:executing-plans

**Goal:** Let users validate the composite-score strategy against historical data — pick universe, date range, top-N, rebalance cadence. Return equity curve, Sharpe, max drawdown, annualized return, vs SPY/Nifty benchmark.

**Architecture:** FastAPI `POST /backtest` → loads historical OHLCV via yfinance (cached in Parquet) + historical scores from `score_cache` snapshots (daily rows). `backtrader` runs strategy in-process (solo dev scale, ≤ 10yr × 500 tickers fits in RAM). Results streamed back as JSON (equity curve array + summary stats). Frontend `/backtest` plots via recharts.

---

## File Map

| File | Change |
|---|---|
| `apps/api/pyproject.toml` | add `backtrader>=1.9.78`, `pyarrow>=15` |
| `apps/api/src/nq_api/backtest/__init__.py` | NEW |
| `apps/api/src/nq_api/backtest/loader.py` | NEW — cached OHLCV + historical score loader |
| `apps/api/src/nq_api/backtest/strategy.py` | NEW — `TopNComposite(bt.Strategy)` |
| `apps/api/src/nq_api/backtest/engine.py` | NEW — `run_backtest(params) -> BacktestResult` |
| `apps/api/src/nq_api/routes/backtest.py` | NEW — POST /backtest with `enforce_tier_quota("backtest")` |
| `apps/api/src/nq_api/schemas_backtest.py` | NEW — request/response |
| `apps/web/src/app/backtest/page.tsx` | NEW — form + result charts |
| `apps/web/src/components/EquityCurveChart.tsx` | NEW — recharts line |
| `apps/web/src/lib/api.ts` | add `runBacktest` to authedApi |
| `sql/005_score_cache_history.sql` | NEW — partitioned-by-day score snapshots for point-in-time correctness |
| `scripts/snapshot_score_cache.py` | NEW — called by nightly GHA to append to history table |

---

## Task 1: Historical score table

- [ ] `sql/005_score_cache_history.sql`:
```sql
CREATE TABLE IF NOT EXISTS public.score_cache_history (
  ticker TEXT NOT NULL,
  market TEXT NOT NULL,
  snapshot_date DATE NOT NULL,
  composite_score NUMERIC,
  rank_score INT,
  sector TEXT,
  current_price NUMERIC,
  PRIMARY KEY (ticker, market, snapshot_date)
);
CREATE INDEX idx_sch_date ON public.score_cache_history(snapshot_date DESC);
ALTER TABLE public.score_cache_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY sch_public_read ON public.score_cache_history FOR SELECT USING (true);
```
- [ ] Extend `nightly_score.py` (Pillar B) to additionally append today's rows to history.

## Task 2: Loader

- [ ] `backtest/loader.py`:
  - `load_ohlcv(tickers, start, end) -> dict[ticker, DataFrame]` — yfinance batch, cache to `.cache/ohlcv/{ticker}.parquet` keyed on `(ticker, end_date)`.
  - `load_scores(tickers, start, end) -> DataFrame` — from `score_cache_history`, forward-fill missing days to next snapshot (point-in-time safe).
  - Reject backtest start-date earlier than earliest snapshot.

## Task 3: Strategy

- [ ] `backtest/strategy.py`:
```python
class TopNComposite(bt.Strategy):
    params = (("top_n", 10), ("rebalance_days", 21))
    def __init__(self):
        self.counter = 0
        self.scores = self.p.scores   # dict[date, dict[ticker, score]]
    def next(self):
        if self.counter % self.p.rebalance_days == 0:
            today = self.data.datetime.date(0)
            ranked = sorted(self.scores.get(today, {}).items(), key=lambda x: -x[1])[: self.p.top_n]
            target_weight = 1.0 / self.p.top_n
            current = {d._name for d in self.datas if self.getposition(d).size}
            picks = {t for t, _ in ranked}
            for d in self.datas:
                if d._name in picks:
                    self.order_target_percent(data=d, target=target_weight)
                elif d._name in current:
                    self.close(data=d)
        self.counter += 1
```

## Task 4: Engine

- [ ] `backtest/engine.py`:
```python
def run_backtest(params) -> BacktestResult:
    cerebro = bt.Cerebro()
    for ticker, df in load_ohlcv(params.tickers, params.start, params.end).items():
        cerebro.adddata(bt.feeds.PandasData(dataname=df, name=ticker))
    scores = load_scores(...)
    cerebro.addstrategy(TopNComposite, top_n=params.top_n, rebalance_days=params.rebalance_days, scores=scores)
    cerebro.broker.setcash(params.initial_cash)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="ret")
    cerebro.addobserver(bt.observers.Value)
    result = cerebro.run()[0]
    # pull equity curve from observer
    # compute vs-benchmark by running a second Cerebro with 100% SPY or NIFTYBEES
    return BacktestResult(...)
```

## Task 5: Schemas

- [ ] `schemas_backtest.py`:
```python
class BacktestRequest(BaseModel):
    market: Literal["US","IN"]
    start_date: date
    end_date: date
    top_n: int = Field(10, ge=3, le=30)
    rebalance_days: int = Field(21, ge=5, le=90)
    initial_cash: float = 100000

class BacktestResult(BaseModel):
    equity_curve: list[tuple[date, float]]
    benchmark_curve: list[tuple[date, float]]
    total_return_pct: float
    annualized_return_pct: float
    sharpe: float
    max_drawdown_pct: float
    benchmark_total_return_pct: float
    trades: int
```

## Task 6: Route

- [ ] `routes/backtest.py`:
```python
@router.post("/backtest", response_model=BacktestResult)
def run(req: BacktestRequest, user: User = Depends(enforce_tier_quota("backtest"))) -> BacktestResult:
    # Cap date range at 10 years. Cap top_n<=30.
    # Kick off run_backtest, return.
    ...
```
- [ ] Tier gate: `free` tier has 0 backtests/day → 403 with upgrade prompt.

## Task 7: Frontend

- [ ] `/backtest/page.tsx` form: market select, date pickers, top_n, rebalance slider, submit.
- [ ] On response: render equity curve + benchmark curve (recharts `LineChart`, two series).
- [ ] Cards: Total Return, Annualized, Sharpe, Max DD, vs Benchmark delta.

## Task 8: Tests

- [ ] `test_backtest_engine.py` — tiny synthetic 30-day OHLCV + scores, assert result shape + no crash.
- [ ] `test_backtest_quota.py` — free tier returns 403; investor tier under cap passes.
- [ ] Smoke: 2020-01-01 → 2025-01-01 US top-10 monthly, assert Sharpe > 0.5 and benchmark delta computed.

## Risks

- **Point-in-time leakage** — critical that score at date T uses only data known at T. `load_scores` must forward-fill FROM prior snapshots, not interpolate across.
- **Survivorship bias** — our universe JSON is current-day; ticker delistings skew results. Mitigation: flag in UI "results exclude delisted names; real alpha may be lower."
- **Compute cost** — 10yr × 500 tickers × daily rebalance = big. Cap at monthly rebalance default, limit `top_n <= 30`. Run async with FastAPI BackgroundTasks + poll endpoint.
- **yfinance rate limits** — cache OHLCV to parquet, share cache across runs.

## Success metrics

- p95 backtest latency (5yr, US top-10, monthly) < 8s
- Sharpe differs less than 0.05 between two runs of same params (deterministic)
- Frontend chart renders within 1s of API response
- Quota enforcement: free=0, investor=5/day, pro=50/day, api=1000/day
