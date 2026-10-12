# Phase 0B — Stop the Bleed + Validate Demand

**Date:** 2026-09-05  
**Verification agent:** testing-reality-checker (main agent execution, agency-lens review)  
**Status:** IN PROGRESS — cleanup code shipped and pushed; demand validation tasks remain.

---

## Cleanup Shipped

| # | Change | File(s) | Evidence |
|---|---|---|---|
| 1 | Removed performance claim from README | `README.md` | Dropped “+13.5% avg alpha vs Nifty50, ~89% hit rate” |
| 2 | Removed synthetic Q1FY27 public backtest | `apps/api/src/nq_api/routes/testing.py` | Deleted `_q1fy27_baseline()`; `/public-results` now returns unavailable notice + SEBI disclaimer |
| 3 | Hidden backtest section from landing | `apps/web/src/components/landing/LandingPage.tsx` | Removed `BacktestResultsSection` import and usage |
| 4 | Hidden Q1FY27 backtest from methodology | `apps/web/src/app/methodology/page.tsx` | Removed section, FAQ, animation hook |
| 5 | Phase tracker updated | `docs/verify/STATUS.md` | Phase 0A complete, Phase 0B in progress |
| 6 | Audit source preserved | `NEURALQUANT_MASTER_REPORT_AUDIT_GB` | Added to repo root |

---

## Verification

- `python -m pytest` from repo root: **178 passed, 10 warnings** (warnings pre-existing, not blocking).
- `cd apps/web && npm run build`: **clean**, 41 pages generated.
- Commit **`9a8fd6d`** pushed to `origin/master` (`964d983..9a8fd6d`).

---

## Remaining Phase 0B Tasks

| # | Task | Status | Notes |
|---|---|---|---|
| B.5 | Scrub remaining Buy/Sell/recommendation language | 🟡 NOT STARTED | Audit `VerdictBanner`, portfolio panels, sell-signal UIs |
| B.6 | Add “not investment advice” notices | 🟡 NOT STARTED | Some pages already have disclaimers; verify coverage |
| B.7 | Employment/QuantAlpha JV IP check | 🔴 BLOCKED ON USER | User must provide documents |
| B.8 | Build 40-prospect list | 🟡 NOT STARTED | SEBI register + US newsletter sources |
| B.9 | Create 100-claim evaluation corpus | 🟡 NOT STARTED | Target: `data/verify/evaluation_corpus_v1.jsonl` |

---

## Active Blockers

1. **Live API throttled earlier.** Render cold-start/rate-limiting prevented final IN-name probe. Re-check after deploy settles.
2. **Employment contract / QuantAlpha JV documents are user-held.** Cannot clear IP/conflict-of-interest checklist without them.

---

## Gate Decision

Phase 0B is **IN PROGRESS**. The regulatory-exposure cleanup portion is complete and deployed. Demand-validation work (prospects, corpus, IP review) has not yet started and is gated on user input for documents and prospect targets.

---

## Next Actions

1. Re-verify live IN readable names after Render deploy settles (probe TCS.NS, RELIANCE.NS, INFY.NS).
2. Audit site copy for remaining recommendation language.
3. Build 40-prospect list and 100-claim evaluation corpus.
4. Request user to provide employment contract and any QuantAlpha JV paperwork.
