# Phase 0A — Foundation Lock Baseline Report

**Original pass:** 2026-10-12 (AEDT), commit `964d983`. The gate was closed on 2026-10-13 in `bda7f15`.
**Updated:** 2026-10-22, against master `5d642dd`, using the public probes from progress review 3 (2026-10-22 01:04–01:10 UTC).
**Status:** CONDITIONAL (India prices are not fresh live; A4 universe probe and A5 docs check not done).

The 2026-10-12 version of this memo carried a September date and declared the gate passed over a table with partial and pending rows. That verdict is withdrawn. This memo replaces it.

---

## What the 2026-10-12 pass actually did

| # | Item | Result on 2026-10-12 |
|---|---|---|
| 1 | Root pytest | `pyproject.toml` had no `testpaths`, so `python -m pytest` at the root collected 0 items. `testpaths = ["apps/api/tests", "packages"]` was added; the root run then gave 178 passed. That is the root collection, not the full suite (see `docs/verify/STATUS.md`, "Test count definition"). |
| 2 | Next.js build | `cd apps/web && npm run build` compiled. |
| 3 | 50 IN tickers, price and change | Not completed. The live API stopped answering during the probe. |
| 4 | 50 US tickers | Not run as a 50-ticker probe. Two names (NVIDIA Corporation, Apple Inc.) were seen live. |
| 5 | IN readable names | Code path present (`_name_from_universe`, `data/universe/in_nifty200.json`); live API still returned the ticker as the name. |
| 6 | README / OPERATIONS / ARCHITECTURE versus live stack | Keyword check only. Not compared with `render.yaml`. |

## State on 2026-10-22

Full suite (five directories, as defined in STATUS): 252 passed. CI on `5d642dd` is green.

India quotes, live `GET /stocks/{t}/meta?market=IN`:

| Ticker | cached_at | stale | current_price | quote_status |
|---|---|---|---|---|
| TCS | 2026-09-03T01:04:47Z | true | null | quote_stale |
| RELIANCE | 2026-09-03T01:04:47Z | true | null | quote_stale |
| INFY | 2026-09-03T01:04:47Z | true | null | quote_stale |
| HDFCBANK | 2026-09-03T01:04:47Z | true | null | quote_stale |

Names for these four now resolve to company names (for example "Tata Consultancy Services Ltd."). The API withholds the old price correctly. The underlying data is still the 2026-09-03 snapshot because the India feeder has not refreshed it. That is a founder / GCP item.

## Gate decision

**CONDITIONAL** (what is missing):

- Fresh India prices. `cached_at` for TCS, RELIANCE, INFY, HDFCBANK was still 2026-09-03 on 2026-10-22, with `stale: true` and price null.
- A4: the 50 US + 50 IN probe (`scripts/verify/probe_universe.py`, task T11).
- A5: README, OPERATIONS, HANDOVER checked against `render.yaml`.

Status for each row lives in `docs/verify/STATUS.md`. If this memo and STATUS disagree, STATUS wins and this memo is wrong.
