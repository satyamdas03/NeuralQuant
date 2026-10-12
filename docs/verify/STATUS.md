# NeuralQuant Verify — Execution Status Tracker

**Current phase:** Phase 0B — Stop the Bleed + Validate Demand  
**Started:** 2026-09-05  
**Goal:** Clean regulatory exposure and confirm licensed publishers will pay before building MVP code.

---

## Phase 0A Gate — Foundation Lock

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Full pytest passes (178/178 expected) | ✅ PASS | `python -m pytest` → 178 passed |
| 2 | Next.js build clean | ✅ PASS | `npm run build` clean |
| 3 | 50 random IN tickers show non-null price/change_pct/name | ⚠️ CONDITIONAL | Price/change present; readable name fixed in code, pending live deploy |
| 4 | 50 random US tickers show non-null price/change_pct/name | ✅ PASS | Readable names present live |
| 5 | README/OPERATIONS/HANDOVER match live stack | ✅ PASS | Keywords and scope match |
| 6 | `testing-reality-checker` memo: PASS | ✅ PASS | `docs/verify/phase_memos/phase_0a_baseline_report.md` |

**Gate result:** CONDITIONAL PASS — live IN name verification pending deploy.

---

## Phase 0B Work in Progress

| # | Task | Status | Notes |
|---|---|---|---|
| B.1 | Remove performance claims from README | ✅ DONE | Removed +13.5% alpha / ~89% hit rate |
| B.2 | Remove `/testing/quarterly/public-results` fallback | ✅ DONE | `_q1fy27_baseline()` deleted; returns unavailable notice |
| B.3 | Hide landing page backtest section | ✅ DONE | `BacktestResultsSection` removed from `LandingPage.tsx` |
| B.4 | Hide methodology backtest section + FAQ | ✅ DONE | Q1FY27 section removed |
| B.5 | Scrub remaining Buy/Sell/recommendation language | 🟡 IN PROGRESS | Need to audit `VerdictBanner`, portfolio, sell-signal panels |
| B.6 | Add "not investment advice" notices | 🟡 IN PROGRESS | Some pages already have disclaimers |
| B.7 | Read employment contract + QuantAlpha JV | 🔴 BLOCKED ON USER | Documents not in repo |
| B.8 | Build 40-prospect list | 🟡 NOT STARTED | Need SEBI register + US newsletter sources |
| B.9 | Create 100-claim evaluation corpus | 🟡 NOT STARTED | Will create `data/verify/evaluation_corpus_v1.jsonl` |

---

## Per-Phase Log

| Phase | Start | End | Gate Result | Memo |
|---|---|---|---|---|
| 0A — Foundation Lock | 2026-09-05 | 2026-09-05 | CONDITIONAL PASS | `docs/verify/phase_memos/phase_0a_baseline_report.md` |
| 0B — Stop the Bleed + Validate Demand | 2026-09-05 | — | IN PROGRESS | — |
| 1 — Verify MVP Core | — | — | NOT STARTED | — |
| 2 — Pilots, Pricing & Patent | — | — | NOT STARTED | — |
| 3 — Scale, Complete Spec, 5 Customers | — | — | NOT STARTED | — |
| 4 — Platform Expansion | — | — | NOT STARTED | — |
| 5 — Strategic Outcome | — | — | NOT STARTED | — |

---

## Active Blockers

1. **Live API throttled / IN names pending deploy.** Paused live probing after API became unresponsive. Will re-check after next deploy.
2. **Employment contract and QuantAlpha JV are user-held documents.** Cannot check IP/conflict without user providing them.

---

## Notes

- All agency-agent mappings live in `docs/verify/AGENCY_AGENT_MAP.md`.
- Master plan lives in `docs/verify/NEURALQUANT_VERIFY_MASTER_PLAN.md`.
- If user says pause, stop immediately, commit/push, and update this file.
