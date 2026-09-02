# NeuralQuant — Bug History (Sessions 8–110c)

> This catalog is published deliberately. It is the engineering maturity record
> of this codebase: every yfinance failure mode, JSON serialization edge,
> timeout boundary, and India-market quirk has already been found and fixed.
> A team rebuilding this product rediscovers this list the hard way.
>
> 150+ bugs were fixed across 110+ documented build sessions (Nov 2024 – Sep 2026).
> This file groups them by root-cause class with the highest-value entries;
> per-session detail lives in the session-by-session commit history.

## The 8 root-cause classes (and the systematic fixes that closed them)

### Class 1 — yfinance fragility on cloud IPs (~25 bugs)
The single largest source of production failures. Now closed by
`packages/data/src/nq_data/price/yf_guard.py`, the only permitted yfinance
entry point.

| Failure mode | Fix |
|---|---|
| 401/403 on Render/GHA cloud IPs | curl_cffi Chrome impersonation session |
| "Invalid Crumb" 401 | retryable-error detection + backoff (3 attempts) |
| MultiIndex column crashes after `yf.download` | `flatten_columns()` |
| Missing `.NS` suffix for India tickers | `normalize_ticker()` — suffix IN exactly once, never US |
| `.NS`-suffixed keys poisoning caches | `bare_ticker()` — cache keys are always bare |
| Infinite hangs (no default timeout) | hard 20s timeout on every call |
| Hopeless on Render | `RENDER=true` → return None, caller falls to FMP/cache |
| news headline under `title` OR `content.title` | normalized in `yf_guard.news()` |

### Class 2 — NaN/Inf JSON serialization crashes
`float('nan')` in any response body 500'd the route (Starlette json.dumps).
Closed by `NaNSanitizerMiddleware` in `main.py`: every JSON response is
recursively cleaned (NaN/Inf → null). Supabase writes go through
`_sanitize_floats()` for the same reason (PostgREST rejects NaN).

### Class 3 — column-name mismatches (silent wrong data)
`composite` vs `composite_score` (all stocks scored identical 5/10),
`composite_at` vs `computed_at`, `nifty_1m_return` vs `nifty_return_1m`
(India regime always "Bear"), quantfactor schema drift. Closed by
`nq_api/db_columns.py` — single source of truth, with a test that parses the
SQL migrations and asserts every constant exists.

### Class 4 — timeout literals too short for Render (~20 bugs)
Anthropic client default-infinite hangs, 22s enrichment cut-offs, OpenBB
30–60s cold starts dropped by 10s connects. Closed by `nq_api/timeouts.py` —
all values are the FINAL tuned numbers; every one was raised after a
production failure. Do not lower them.

### Class 5 — US/IN market branching (~15 bugs)
US macro used for India regime, `^GSPC` beta for NIFTY stocks, un-suffixed
yfinance symbols, `.NS`-suffixed tickers failing `len(t) > 8` validation
(RELIANCE.NS = 11 chars → all India stocks silently skipped → 503s).
Regression wall: `apps/api/tests/test_market_branching.py`.

### Class 6 — stale/empty cache cascades
score_cache went 46 days stale (upsert conflict swallowed) → every downstream
endpoint degraded. Fixes: `resolution=merge-duplicates` upsert, DELETE+INSERT
rebuild, forced rebuild on cold start, and `/health` now exposes
`score_cache_age_hours` + row count so staleness is observable.

### Class 7 — garbage tickers at ingestion
Excel legend rows ("DARK GREEN", "SCORE") ingested as tickers from the Anjali
workbook; screener showed them to users. Closed by the single
`is_valid_ticker()` in `packages/data/src/nq_data/ticker_validation.py`
(regex + legend-word blocklist, handles M&M and BAJAJ-AUTO).

### Class 8 — async/sync boundary + format-string crashes
Blocking yfinance/Supabase calls inside the event loop (uvicorn stalls,
`httpx.RemoteProtocolError` from supabase-py — replaced with direct PostgREST
httpx); five `ValueError` crashes from `%`-formatting in strings containing
`>%5min` patterns.

### Class 9 — score-scale / normalization family
`score_cache.composite_score` was stored as quantfactor composite × 10
(−160..+160) while consumers assumed 0–1. Result: every trade Kelly edge=1.0,
meta scores pegged 10/10, backtest hit rate garbage (−3271%). Fixed by a single
`score_builder.normalize_cache_composite()` and auditing every consumer.
Factor scores were also floored at 0, zeroing quality/momentum in down markets;
replaced with true cross-sectional percentile ranks.

### Class 10 — India-market data completeness
Render outbound IPs blocked by Yahoo → IN prices dropped. Mitigation became a
dedicated GCP e2-micro India price feeder (`infra/gcp/india_feed.py`) that
writes to `stock_snapshot`. `.NS`/`.BO` normalization moved to a single shared
path in `snapshot_cache.py` and `score_cache.py` so `/stocks/{ticker}?market=IN`,
`/screener?market=BOTH`, and nightly_score all agree on ticker keys.

### Class 11 — infrastructure churn
Railway trial expired → Hermes migrated to GCP Always Free e2-micro VM.
ElevenLabs/Sarvam voice TTS replaced by LiveKit Inference (cartesia/sonic-3.5).
Email functionality fully removed (Resend, DKIM, market-wrap emails); migrations
027–029 are queued, with 028 unblocked in Session 110c by removing `email_sent`
references from `session.py`. Render auto-deploy now enabled.

### Class 12 — in-process scheduler cold-start herd
Startup market refresh could fire from multiple simultaneous instances/restarts.
Fixed with `NQ_SCHEDULER_MASTER` env gate, random startup jitter, and a
per-process one-hour cold-start debounce.

## Selected chronology (high-signal incidents)

| Session | Incident | Root cause |
|---|---|---|
| 8 | India stocks 503 | missing IN data path |
| 15 | OOM on Render | unbounded DataFrame caches |
| 22 | NVDA hallucinated P/E | LLM ignored injected data → [VERIFIED] markers + metric validation |
| 31 | yfinance 401 wave | cloud-IP block → curl_cffi + 1h info cache |
| 38 | Penny stocks in movers | no price filter → $5 floor |
| 42–44 | Terminal 504 ×3 | OpenBB Render cold start → keep-warm + fast-connect detect + retry ladder |
| 53–54 | Ask AI "data not injected" | 22s enrichment timeout (v2 outlier) → 45s + entity labels |
| 59 | GHA nightly ran 6 hours | 4 unguarded yfinance paths + `np.isfinite` on mixed dtypes |
| 76 | score_cache 46 days stale | silent upsert conflict |
| 80b | 8 production crashes in one day | NaN serialization + tier query + rename fallout |
| 81 | All stocks identical scores | `composite` vs `composite_score` |
| 82 | TCS/RELIANCE/INFY 503 | `.NS`-suffixed universe keys + `len > 8` filter |
| 84 | Sale-ready acceptance test | Docker stack CORS/NaN middleware strip → hardened acceptance runbook |
| 90–91 | Branding + live price parity | QuantAlpha→NeuralQuant; OpenBB yfinance proxy for live prices |
| 92–93 | Security P0–P6 | RLS, IDOR, headers, CSP, audit log, gitleaks/dependency scanning |
| 94 | Demo badge/nav bugs | loss-growth flag misread as profit level; CSP/console; auth nav state |
| 100–101 | Hermes paper-trading collapse | no trend filter + open-loop reflection + SPOF exchange → multi-exchange + telemetry + revert guard |
| 102 | Factor scores floored at 0 | `max(0, val/4)` killed negatives → cross-sectional pct rank |
| 104 | Score-scale bug family | composite stored qf×10 vs consumers expecting 0–1 |
| 106–109 | Render→GCP + stale docs | Railway expiration, Resend/email removal, version/smoke/test count drift, IN screener merge bugs |
| 110 | Health sweep + IN feeder enrichment | docs refresh drift; `score_cache` default cols missing `growth_percentile`/`score_1_10`/regime; scheduler cold-start herd |
| 110b | Residual score-scale sweep + quality fix | four cache consumers still bypassed `normalize_cache_composite`; `quality_percentile` duplicated `growth_percentile` |
| 110c | Operator runbook + email schema unblock | migration 028 blocked by `session.py` `email_sent` refs; `ADMIN_EMAILS` env wiring |

## Known open items (disclosed)

- `/query/v2` deep-dive can exceed 60s on Render (multi-agent PARA-DEBATE);
  mitigations in place, async-polling redesign documented in OPERATIONS.md.
- DII/FII flows are market-aggregate proxy, not per-stock.
- CSP remains report-only until violation collector confirms no false positives.
- No persistent Ask Morgan memory — sliding-window context, lost on refresh.
- India HMM regime is still heuristic (VIX thresholds); fitted HMM on NIFTY
  returns is the planned evolution.
- Supabase migrations 027–029 pending; migration 028 is now unblocked after
  removing `email_sent` references from `session.py`.
- GCP India price feeder is built and ready; pending install/schedule on the VM.
- Render `quantastra-agent` manual deploy pending.
- Railway cleanup pending (old Hermes Railway service still to be deleted).
- Key rotation pending.
- `ADMIN_EMAILS` value pending on the Render dashboard (already wired in
  `render.yaml` and `.env.example`).
