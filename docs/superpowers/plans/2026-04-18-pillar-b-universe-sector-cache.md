# Pillar B Implementation Plan — Universe Expansion + Sector-Adjusted Factors + Nightly Cache

> superpowers:executing-plans

**Goal:** Scale scoring to 500 US + 200 NSE tickers with sector-normalized factor ranks, cached overnight so the screener responds in <100ms.

**Architecture:**
1. Static JSON universe files refreshed monthly by GitHub Actions.
2. Factor compute adjusted to rank within GICS sector cohorts (not cross-universe).
3. Nightly GitHub Actions cron → computes all scores → writes `public.score_cache`.
4. `/screener` reads from cache; falls back to live compute only when cache stale (> `tier.screener_refresh_seconds`).

---

## File Map

| File | Change |
|---|---|
| `data/universe/us_sp500.json` | NEW — top 500 US tickers + GICS sector + subindustry |
| `data/universe/in_nifty200.json` | NEW — Nifty 200 constituents + NIC sector |
| `apps/api/src/nq_api/universe.py` | load JSON, keep US_DEFAULT/IN_DEFAULT for back-compat, add `UNIVERSE_FULL` + `sector_of(ticker)` |
| `apps/api/src/nq_signals/score_engine.py` | sector-aware percentile ranking (group-by sector) |
| `apps/api/src/nq_api/cache/score_cache.py` | NEW — read/write Supabase `score_cache` table |
| `apps/api/src/nq_api/routes/screener.py` | read from cache, TTL per tier |
| `scripts/refresh_universe.py` | NEW — pulls S&P 500 + Nifty 200 from Wikipedia/NSE CSV |
| `scripts/nightly_score.py` | NEW — computes all scores, upserts score_cache |
| `.github/workflows/nightly-score.yml` | NEW — cron `0 2 * * *` UTC |
| `.github/workflows/monthly-universe.yml` | NEW — cron `0 3 1 * *` |
| `sql/003_score_cache.sql` | NEW — score_cache table + indexes |

---

## Task 1: Universe JSON + loader

- [ ] `data/universe/us_sp500.json` shape:
```json
[{"ticker":"AAPL","name":"Apple Inc.","sector":"Information Technology","subindustry":"Technology Hardware, Storage & Peripherals","market_cap_bucket":"mega"}, ...]
```
- [ ] Same shape for `in_nifty200.json` with sector labels from NSE classification (Financial Services, IT, Oil & Gas, Auto, Pharma, FMCG, Metals, etc.).
- [ ] Extend `universe.py`:
  - `_load(path)` parses JSON → list[dict].
  - `UNIVERSE_FULL = {"US": _load("us_sp500.json"), "IN": _load("in_nifty200.json")}`.
  - `sector_of(ticker, market) -> str`.
  - Preserve `US_DEFAULT`, `IN_DEFAULT`, `UNIVERSE_BY_MARKET` (derive from UNIVERSE_FULL → just ticker list).

- [ ] Test: assert `len(US_DEFAULT) >= 500`, `len(IN_DEFAULT) >= 200`.

## Task 2: `refresh_universe.py`

- [ ] Scrape Wikipedia `List_of_S%26P_500_companies` (pandas.read_html) → dedupe → write JSON.
- [ ] Pull Nifty 200 from `https://archives.nseindia.com/content/indices/ind_nifty200list.csv` with a browser User-Agent header.
- [ ] Commit to `data/universe/` only on diff. Open auto-PR with label `universe-refresh`.

## Task 3: Sector-adjusted factor ranks

- [ ] In `score_engine.compute`, replace cross-universe `rankdata` with:
```python
df["value_percentile"] = df.groupby("sector")["value_z"].transform(
    lambda s: s.rank(pct=True, method="average")
)
# repeat for momentum, quality, low_vol, short_interest
```
- [ ] Fallback to cross-universe rank when sector cohort has < 5 members.
- [ ] Add `sector` column to snapshot via `sector_of` lookup.
- [ ] Tests: sector-isolated rank (2 tech stocks, 2 energy stocks → each ranks within its sector).

## Task 4: SQL score_cache

- [ ] `sql/003_score_cache.sql`:
```sql
CREATE TABLE IF NOT EXISTS public.score_cache (
  ticker TEXT NOT NULL,
  market TEXT NOT NULL CHECK (market IN ('US','IN')),
  sector TEXT,
  composite_score NUMERIC,
  rank_score INT,
  value_percentile NUMERIC,
  momentum_percentile NUMERIC,
  quality_percentile NUMERIC,
  low_vol_percentile NUMERIC,
  short_interest_percentile NUMERIC,
  current_price NUMERIC,
  analyst_target NUMERIC,
  pe_ttm NUMERIC,
  market_cap NUMERIC,
  week52_high NUMERIC,
  week52_low NUMERIC,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (ticker, market)
);
CREATE INDEX idx_score_cache_market_score ON public.score_cache(market, composite_score DESC);
ALTER TABLE public.score_cache ENABLE ROW LEVEL SECURITY;
-- anon can read
CREATE POLICY score_cache_public_read ON public.score_cache FOR SELECT USING (true);
```

## Task 5: Cache read/write helpers

- [ ] `cache/score_cache.py`:
  - `read_top(market, n=50, max_age_seconds=3600)` → sorted desc by composite_score.
  - `upsert_scores(rows: list[dict])` via service-role upsert.
  - `fallback_to_live(market)` → if cache stale/missing, trigger on-demand build_real_snapshot for top 50.

## Task 6: Wire screener to cache

- [ ] In `routes/screener.py`, before live compute:
  ```python
  age_cap = TIER_LIMITS[user.tier].screener_refresh_seconds if user else 3600
  cached = score_cache.read_top(market, n=500, max_age_seconds=age_cap)
  if cached: return cached
  # else live compute (current path)
  ```

## Task 7: `nightly_score.py`

- [ ] Script iterates full universe in chunks of 50, calls `build_real_snapshot` + `engine.compute` + `rank_scores_in_universe`, assembles rows, `upsert_scores`.
- [ ] Guard: skip ticker if live fetch fails; log count of successes.
- [ ] Use `SUPABASE_SERVICE_ROLE_KEY`.

## Task 8: GitHub Actions

- [ ] `.github/workflows/nightly-score.yml`:
```yaml
name: nightly-score
on:
  schedule: [{cron: "0 2 * * *"}]  # 02:00 UTC daily
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install uv && uv sync --all-packages
      - run: uv run python scripts/nightly_score.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          FRED_API_KEY: ${{ secrets.FRED_API_KEY }}
```
- [ ] `monthly-universe.yml` — cron `0 3 1 * *`, runs `refresh_universe.py`, creates PR via peter-evans/create-pull-request.

## Task 9: Benchmark + fallback

- [ ] Smoke test: hit `/screener?market=US` after cache populated → target p95 < 100ms.
- [ ] Stop cache → verify fallback to live compute still works (degraded latency, but correct).

## Risks

- **Wikipedia scrape breakage** — cache the last good list; fallback if parse fails.
- **NSE user-agent blocks** — use `Mozilla/5.0` UA and retry with backoff.
- **Cost** — nightly compute ≈ 700 yfinance lookups. Respect `time.sleep(0.25)` between calls to avoid rate-limit.
- **Sector cohort too thin** — fallback to cross-universe rank triggers automatically for sectors with < 5 stocks.

## Success metrics

- Screener p95 < 100ms (was ~60s for live compute of 25 tickers)
- Universe coverage: 500 US + 200 NSE confirmed via `/screener?full=true` count
- Nightly GHA success rate > 95% over rolling 7 days
- Sector rank sanity: top 10 IT stocks no longer dominated by mega-caps only
