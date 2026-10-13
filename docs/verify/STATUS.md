# NeuralQuant Verify — Execution Status Tracker

**Current phase:** Phase 0-SEC  
**Started:** 2026-10-13  
**Goal:** Close high-severity security and correctness holes before any pivot sales or product work.

---

## Active Status Values

Allowed values for each item: `NOT STARTED` / `IN PROGRESS` / `MERGED-NOT-DEPLOYED` / `VERIFIED-LIVE` / `BLOCKED` / `CONDITIONAL`.

---

## Phase 0-SEC — Security and Correctness

| # | Task | F-ID | Status | Commit | Test Summary | Live Evidence |
|---|---|---|---|---|---|---|
| S0 | Remove audit dump from repo root | — | **VERIFIED-LIVE** | `26bc004` | N/A | `git ls-files NEURALQUANT_MASTER_REPORT_AUDIT_GB` → empty; no live surface. |
| S1 | Auth on `POST /live/classify` and `POST /trade/backtest` | F-07, F-08 | **MERGED-NOT-DEPLOYED** | `b48c835` | 209 passed, 19 warnings | `/health` still `version: 4.1.3`; `POST /live/classify` → 200 (expected 401); `POST /trade/backtest` → 422 (expected 401). **Render deploy pending.** |
| S2 | Unknown ticker → 404, never score 10 | F-02 | **MERGED-NOT-DEPLOYED** | `02aa8ce` | 213 passed, 19 warnings | `/health` still `version: 4.1.3`; `GET /stocks/NOTAREALTICKERXYZ?market=US` → 200 (expected 404). **Render deploy pending.** |
| S3 | India freshness: stale from `cached_at`, badge/refuse | F-01, F-14 | **MERGED-NOT-DEPLOYED** | `7b3bd64` | 216 passed, 19 warnings | `/health` still `version: 4.1.3`; `GET /stocks/TCS.NS/meta?market=IN` returns `cached_at=2026-09-03`, `stale=false` (expected `stale=true`). **Render deploy pending.** |
| S4 | Ask AI blank summary → 502; length/history caps; prompt fence | F-03, F-04 | **MERGED-NOT-DEPLOYED** | `d632e33` | 219 passed, 19 warnings | `/health` still `version: 4.1.3`. Live blank-summary behavior unchanged until deploy. **Render deploy pending.** |
| S5 | CI runs full pytest; remove `--exit-zero` | F-19 | **MERGED** | `41a4341` | 199 passed, 10 warnings | `uv run ruff check packages/ apps/api/` → 0 errors; `python -m pytest` → 199 passed. CI workflow now has `test` job and ruff no longer uses `--exit-zero`. No deploy needed. |
| S6 | Secret scan table; rotation by Satyam | F-24 | **MERGED-NOT-DEPLOYED** (docs-only; no deploy needed) | `a0b876e` | N/A | `docs/verify/evidence/secret_scan_2026-10-13.md`. No secret values printed. Owner rotation pending. |
| S7 | Upgrade runtime deps; re-audit | F-16 | NOT STARTED | — | — | — |
| S8 | `secrets.compare_digest`, fail-closed empty `CRON_SECRET` | F-10, F-23 | **MERGED** | `TBD` | 209 passed, 11 warnings | `/cron/*` and `/health/smoke` now use `require_admin_or_cron`; `SMOKE_TEST_SECRET` bypass uses `secrets.compare_digest`. Regression tests: 10 new cases. Live verification blocked by Render 503. |
| S9a | Freeze Hermes page | F-06 | NOT STARTED | — | — | — |
| S9b | Guest LiveKit budget / pause voice | F-22 | NOT STARTED | — | — | — |
| S9c | Remaining medium/low security items | F-09, F-12, F-13, F-15, F-17, F-18, F-21 | NOT STARTED | — | — | — |

---

## Phase 0B — Finish Claim and Advice Scrub, and Deploy It

All Phase 0B work is **blocked until Phase 0-SEC S1 is deployed live**.

| # | Task | Status | Notes |
|---|---|---|---|
| B1 | Make `/testing/quarterly/public-results` return no metrics in all branches | MERGED-NOT-DEPLOYED | Code shipped in `9a8fd6d`; live still serves old fixture at `run_date 2026-06-02`. Need deploy + fix success path. |
| B2 | Remove 87%/Q1FY27 from OG/Twitter and methodology FAQ | NOT STARTED | `apps/web/src/app/page.tsx`, `apps/web/src/app/methodology/layout.tsx` |
| B3 | Scrub README, ARCHITECTURE, ASSET_INVENTORY, pricing cards, prospectus md/scripts | NOT STARTED | README:84 FinDebate, README:97 Q1FY27 pointer, ARCHITECTURE:68, pricing "Proven Edge" etc. |
| B4 | Delete orphaned backtest components and `accuracy()` client | NOT STARTED | 4 components in `apps/web/src/components/landing/`. |
| B5 | Neutralize BUY/SELL/AVOID labels at UI boundary | NOT STARTED | VerdictBanner, AgentDebatePanel, IRSZoneBadge, StockSummaryCard, SellSignalsPanel, portfolio, quantfactor, methodology table. |
| B6 | Freeze Hermes page | NOT STARTED | Remove route or noindex + hide nav. |
| B7 | Add "not investment advice" line on `/pricing` | NOT STARTED | Founder decision on checkout suspension recorded separately. |

---

## Phase 0A — Re-Gate Honestly

Phase 0A status is **CONDITIONAL** until live India probe passes. Memos need date/link corrections.

| # | Task | Status | Notes |
|---|---|---|---|
| A1 | Fix `STATUS.md` link to `docs/NEURALQUANT_VERIFY_MASTER_PLAN.md` | DONE in this file | Was pointing to non-existent `docs/verify/NEURALQUANT_VERIFY_MASTER_PLAN.md`. |
| A2 | Rewrite `phase_0a_baseline_report.md` to CONDITIONAL | NOT STARTED | Memo currently says PASS while table says India pending. |
| A3 | Rewrite `phase_0b_stop_the_bleed.md` to "not deployed" | NOT STARTED | Memo currently says "complete and deployed". |
| A4 | Write `scripts/verify/probe_universe.py` and run 50+50 probe | NOT STARTED | Save CSV to `docs/verify/evidence/`. |
| A5 | Re-gate Phase 0A honestly | NOT STARTED | PASS only if all criteria met with evidence. |

---

## Verify Phase 0 — Demand Validation

| # | Task | Status | Notes |
|---|---|---|---|
| V0 | Build `scripts/verify/check_note.py` | NOT STARTED | Read-only note verifier; no new service. |
| V1 | Test on 3 sample public notes | NOT STARTED | Satyam supplies notes. |
| V2 | One-page B2B offer + pilot description | **IN PROGRESS** | No performance claims. Value = audit log for SEBI/SEC substantiation. |
| V3 | Create `docs/verify/interviews.csv` tracker | **IN PROGRESS** | Satyam fills rows; I never invent data. |

---

## Day-30 Gate

| Metric | Target | Current |
|---|---|---|
| Customer-discovery interviews | 15+ | 0 |
| Pilots running | 3+ | 0 |
| Paying customers ≥$49/mo | 1+ | 0 |

**Decision:** Not reached.

---

## Active Blockers

1. **Render service is live-unhealthy.** `GET https://nq-api.onrender.com/health` returns `{"status":"unhealthy"}` with HTTP 503. This blocks live verification of S1–S4 and all deploy-dependent steps. Satyam must inspect/trigger the Render deploy for service `nq-api`.
2. **Empty/invalid `CRON_SECRET` handling for other cron routes** remains after S1 (F-10, F-23).

---

## Notes

- Test counts: full suite = 209 passed (11 warnings). Ruff now passes with the configured rule set.
- CI now runs `pytest` and ruff without `--exit-zero`.
- Master plan file lives at `docs/NEURALQUANT_VERIFY_MASTER_PLAN.md`.
- Audit dump `NEURALQUANT_MASTER_REPORT_AUDIT_GB` was removed in `26bc004`; history rewrite deferred to owner decision.
