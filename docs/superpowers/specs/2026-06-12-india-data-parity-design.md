# India Data Parity Pipeline — Design (P1)

Date: 2026-06-12 · Status: approved · Repo: anjali-value-stocks (Railway service)

## Problem
quantfactor_universe has 446 US rows (fully automated daily pipeline) but only
~60 IN rows, frozen in a manually-uploaded `stock_analysis_coloured (1).xlsx`.
`collect_indian_data.py` exists but was never automated. FMP Premium blocks
Indian fundamentals; yfinance .NS is partial + rate-limited.

## Approved decisions
- Universe: **NIFTY 500** (P2: + SmallCap 250 + MicroCap 250)
- Sources: **screener.in scrape** (fundamentals + DII/FII shareholding, same
  page) + **NSE bhavcopy** (prices → returns/beta/std)
- Runtime: anjali repo's existing **Railway** scheduler + auto-commit flow

## Pipeline
1. `universe_in.py` — fetch ind_nifty500list.csv from niftyindices.com,
   cache + commit; manual override map for symbol oddities.
2. `collect_indian_data.py` (extended) —
   - screener.in per ticker (rate limit ≥2s, UA, backoff, 24h HTML cache):
     sales/profit YoY + TTM + QoQ, PE, PB, EV/EBITDA, EV/Sales, market cap,
     revenue, shareholding table (DII/FII quarter + 1yr deltas).
   - symbol→slug via screener.in search API; override map for misses.
   - NSE bhavcopy OHLCV → 3M/6M/1Y/2Y returns, Qtr/Yr beta vs NIFTY 50,
     Qtr/Yr std. One-time 2-year backfill on first run.
3. `build_india_sheet.py` (new; mirrors build_us_stock_sheet.py) — quintile
   colors (DG/LG/White/LR/DR) ranked within universe → RETURN/GROWTH/
   VALUATION/RISK scores → `India_Stock_Analysis_Coloured.xlsx`, committed.
4. `scheduler.py` — india job after the US run, daily.
5. NeuralQuant `quantfactor_sync._ensure_india_excel` — prefer
   India_Stock_Analysis_Coloured.xlsx, fall back to the old static sheet
   (zero-risk cutover). Forward PE/PEG stay nullable in P1.

## Safety rails
- Abort commit if <300 rows parse cleanly — never clobber good data.
- Per-ticker failures: skip + log; collection continues.
- Parser tests on fixture HTML; row-count + null-rate checks in
  verify_pipeline.py.

## Risks
screener.in blocking (mitigate: polite rate, stable Railway IP; fallback
yfinance-partial), NSE bhavcopy format drift (parser isolated), slug-mapping
oddballs (override map).
