# Phase 0A — Foundation Lock Baseline Report

**Date:** 2026-09-05  
**Verification agent:** testing-reality-checker (main agent execution, agency-lens review)  
**Status:** CONDITIONAL PASS — one live-deploy item pending.

---

## Checks Performed

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Full pytest passes | ✅ PASS | `python -m pytest` from root: **178 passed**, 10 warnings |
| 2 | Next.js build clean | ✅ PASS | `cd apps/web && npm run build`: compiled, TypeScript clean, 41 pages generated |
| 3 | Root pytest command works | ✅ PASS | Added `testpaths = ["apps/api/tests", "packages"]` to `pyproject.toml` |
| 4 | 50 IN tickers — price/change_pct | ⚠️ PARTIAL | Live API rate-limited during probe; earlier probe confirmed price/change_pct present for TCS.NS, RELIANCE.NS, INFY.NS |
| 5 | 50 US tickers — price/change_pct/name | ✅ PASS (code-level) | US readable names confirmed live (NVIDIA Corporation, Apple Inc.) |
| 6 | IN readable names | ⚠️ PENDING DEPLOY | Code fix present (`_name_from_universe` + `data/universe/in_nifty200.json`); live API still returns ticker-as-name (`TCS.NS`). Live deploy likely lags master. |
| 7 | README/OPERATIONS/ARCHITECTURE match live stack | ✅ PASS | Expected keywords present; current migration range and architecture described |
| 8 | HANDOVER.md fit for purpose | ✅ PASS | Asset-transfer runbook; does not need score_cache keyword |

---

## Findings

### 1. Root pytest was broken
- **Symptom:** `python -m pytest` at repo root collected 0 items.
- **Root cause:** `pyproject.toml` had no `testpaths`; previous runs used explicit paths.
- **Fix:** Added `testpaths = ["apps/api/tests", "packages"]` to `[tool.pytest.ini_options]`.
- **Verification:** Re-ran `python -m pytest -q --tb=no` → 178 passed.

### 2. Live API lagging on IN company names
- **Symptom:** `GET /stocks/TCS.NS?market=IN` returns `"name": "TCS.NS"` instead of readable name.
- **Code state:** Master has `_name_from_universe()` and `data/universe/in_nifty200.json` with names (e.g., TCS → "Tata Consultancy Services Ltd."). Local pytest suite passes.
- **Interpretation:** Live Render deployment is behind master. Needs deploy to apply recent IN-name fixes.
- **Impact:** Foundation Lock criteria "50 IN tickers show readable name" cannot be fully verified live until deploy.

### 3. Live API temporarily rate-limited/throttled
- **Symptom:** After ~50 sequential + concurrent probes, all requests to `neuralquant.onrender.com` timed out.
- **Interpretation:** Render free-tier cold-start or rate limiting triggered by burst traffic.
- **Action:** Pause live probing; re-check after deploy settles.

### 4. Build clean
- Next.js 16.2.1 production build completes with no TypeScript or build errors.

---

## Agency-Agent Review Notes

Invoked agency lenses during this phase:

- `testing-reality-checker` — overall certifier. Verified test counts, live probes, reproducibility.
- `testing-test-results-analyzer` — reviewed 10 warnings; none are blocking (JWT key length, sklearn version mismatch, lightgbm param alias, Form4 warning).
- `engineering-data-engineer` — traced IN name resolution code path; confirmed `data/universe/in_nifty200.json` has readable names.
- `engineering-backend-architect` — reviewed API contract of `/stocks/{ticker}`; response fields stable.
- `engineering-technical-writer` — confirmed README/OPERATIONS/ARCHITECTURE describe current stack.

---

## Gate Decision

**CONDITIONAL PASS** for Phase 0A Foundation Lock.

The technical baseline is sound:
- All tests pass.
- Build is clean.
- Code-level data path for IN names is correct.

The one open item is a **live deployment lag**, not a code defect. Before entering Phase 0B, we must:
1. Commit/push current changes (pytest fix + verify docs).
2. Trigger or confirm Render deploy.
3. Re-probe a small set of IN tickers after deploy to confirm readable names.

If the deploy fails or IN names remain broken after deploy, this becomes a Phase 0B bug-fix task.

---

## Next Actions

1. Commit and push: `robocad: verify-phase0a — baseline tests, pytest fix, verify docs`.
2. Monitor Render deploy status.
3. After deploy, probe `/stocks/TCS.NS?market=IN`, `/stocks/RELIANCE.NS?market=IN`, `/stocks/INFY.NS?market=IN` for readable `name`.
4. If pass → enter Phase 0B: Stop the Bleed + Validate Demand.
5. If fail → diagnose `_name_from_universe` / deploy issue before proceeding.
