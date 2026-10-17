# NeuralQuant Verify — Execution Status Tracker

**Current phase:** Phase 0-SEC
**Started:** 2026-10-13
**Last updated:** 2026-10-18 (Sydney, AEDT). Rewritten for task T1; replaces the 2026-10-13 version, which used disallowed values and wrong counts.
**Goal:** Close high-severity security and correctness holes before any pivot sales or product work.
**Plan:** `docs/NEURALQUANT_VERIFY_MASTER_PLAN.md`

---

## Status values

Allowed values only: `NOT STARTED` / `IN PROGRESS` / `MERGED-NOT-DEPLOYED` / `VERIFIED-LIVE` / `BLOCKED (reason)` / `CONDITIONAL (what is missing)`.

- `VERIFIED-LIVE` needs a public-host curl from the same session in the row. CI items need a GitHub Actions run URL.
- "Merged" is not "live". `version: 4.1.3` in `/health` is hardcoded in `main.py` and proves nothing about deploys.

## Test count definition

Full suite = five directories, run as:

```
uv run python -m pytest apps/api/tests packages/data packages/signals apps/livekit-agent/tests scripts/backtest/tests -q
```

| Directory | Tests (2026-10-18) |
|---|---|
| apps/api/tests | 127 |
| packages/data | 63 |
| packages/signals | 19 |
| apps/livekit-agent/tests | 17 |
| scripts/backtest/tests | 3 |
| **Full suite** | **229** |

Root `uv run pytest` (testpaths = apps/api/tests + packages) collects 209. 209 is **not** the full suite.

History: `53c61a2` 198; after S1–S4 219; `8cdc3e5` 229. No tests were deleted.

Clean-environment note: `apps/api/src/nq_api/main.py` loads `apps/api/.env` with `override=True`. A local run with a populated `.env` therefore hides key-dependent failures. On 2026-10-18, with `.env` loading disabled and `ANTHROPIC_API_KEY` unset, HEAD `8cdc3e5` gave **2 failed / 227 passed** (`test_v2_blank_summary_returns_502`, `test_v2_user_question_wrapped_in_fence`). After the T1 fix, the same clean run gives **229 passed**.

---

## Live evidence, 2026-10-17 23:32 UTC (2026-10-18 10:32 AEDT)

Single unauthenticated GETs against the public hosts only.

| Probe | Result | Meaning |
|---|---|---|
| `GET https://neuralquant.onrender.com/health` | 200 `{"status":"ok","version":"4.1.3","score_cache_age_hours":21.1,"score_cache_rows":944,"demo_mode":false}` | API process up. No outage. |
| `GET /stocks/NOTAREALTICKERXYZ?market=US` | 200 | S2 not deployed |
| `GET /stocks/TCS/meta?market=IN` | 200, `current_price 2348.0`, `cached_at 2026-09-03T01:04:47Z`, `stale:false` | F-01 live |
| `GET /testing/quarterly/public-results` | 200, Q1FY27 fixture, `summary.alpha 13.65`, `hit_rate 88.1`, no `available` key | F-11 live; API build older than `9a8fd6d` |
| `GET /cron/nightly-score/status` (no header) | 401 `{"detail":"Missing Authorization header"}` | Pre-S8 wording |
| `GET https://www.neuralquant.co/` | "87%+ hit rate in Q1FY27 backtest" present in meta | B2 not done |

Earlier 2026-10-17 12:07 UTC probes (handover) agree. The earlier claim that the API returned 503 came from a different hostname (`nq-api.onrender.com`) and was wrong; it has been removed.

**Deploy state:** Render serves a build older than `9a8fd6d` (13 Oct). Vercel serves the 13 Oct web build. Nothing after 13 Oct 09:52 AEDT is live on the API.

---

## Phase 0-SEC — Security and Correctness

| # | Task | F-ID | Status | Commit | Evidence / what is missing |
|---|---|---|---|---|---|
| step-0 | Remove audit dump from repo | F-24 | IN PROGRESS | `26bc004` | Gone from tree; blob still in history at `9a8fd6d`. History rewrite is a founder decision. |
| T1 | Suite green in a clean env; ruff installed; CI on push + PR with full suite | F-19, F-03 tests | IN PROGRESS | T1 commit (this change) | Local clean run 229 passed; `uv run ruff check packages/ apps/api/` exit 0 with ruff 0.16.1 from the project venv. Missing: green Actions run URL for workflow CI, and red-run URL from a throwaway draft PR. |
| S1 | Auth on `POST /live/classify`, `POST /trade/backtest` | F-07, F-08 | MERGED-NOT-DEPLOYED | `b48c835` | No non-admin 403 test; 401 test does not assert pipeline not called; `/live/execute` open to any signed-in user. Not live. |
| S2 | Unknown ticker → 404 | F-02 | MERGED-NOT-DEPLOYED | `02aa8ce` | Score route only; `/meta` unchecked. Live fake ticker → 200 (2026-10-17 23:32 UTC). |
| S3 | India freshness | F-01, F-14 | IN PROGRESS | `7b3bd64` | Wrong threshold (35 min); stale rows still serve price; `last_updated` is request clock; test encodes wrong acceptance. Live TCS `stale:false` with 2026-09-03 `cached_at`. Task T2. |
| S4 | Ask AI blank summary → 502; caps; fence | F-03, F-04 | MERGED-NOT-DEPLOYED | `d632e33` | Tests now pass in a clean env (T1). Timeout/except paths still 200 HOLD; `str(exc)` leak; history unfenced; delimiter unescaped. Task T12. |
| S5 | CI runs real pytest | F-19 | IN PROGRESS | `41a4341` + T1 | Superseded by T1. Not green until an Actions URL exists. |
| S6 | Secret scan; rotation | F-24 | BLOCKED (founder: key rotation not confirmed) | `a0b876e` | Report only: `docs/verify/evidence/secret_scan_2026-10-13.md`. |
| S7 | Upgrade runtime deps | F-16 | NOT STARTED | — | Task T13. |
| S8 | `compare_digest`, fail-closed empty `CRON_SECRET` | F-10, F-23 | MERGED-NOT-DEPLOYED | `7f7430a` | Smoke bypass still mints a pro user in production. Gitleaks flagged a fixture at `apps/api/tests/test_cron_smoke_auth.py:30` (task T1b). Live cron status still pre-S8 wording. |
| S9a | Freeze Hermes page | F-06 | IN PROGRESS | `9140812` | Nav hidden, `noindex`. Page still renders P&L and win rate; banner claims otherwise. Same work as B6. |
| S9b | Guest LiveKit budget / pause voice | F-22 | IN PROGRESS | `f53ab9c` | Constants are never read; guests still dispatched. No test. |
| S9c | Remaining medium/low items | F-09, F-12, F-13, F-15, F-17, F-18, F-21 | NOT STARTED | — | Task T14. |

---

## Phase 0B — Claim and Advice Scrub

| # | Task | Status | Notes |
|---|---|---|---|
| B1 | `/testing/quarterly/public-results` returns no metrics on any branch | MERGED-NOT-DEPLOYED | `9a8fd6d` covers empty/error paths only; success path still returns alpha/hit_rate. No test. Live serves fixture. Task T3. |
| B2 | Remove 87%/Q1FY27 from OG/Twitter and methodology FAQ | NOT STARTED | Live homepage meta still "87%+ hit rate". Task T4. |
| B3 | Scrub README, ARCHITECTURE, ASSET_INVENTORY, pricing, prospectus | NOT STARTED | Task T5. |
| B4 | Delete orphaned backtest components and `accuracy()` | NOT STARTED | Task T6. |
| B5 | Neutralise BUY/SELL/AVOID labels | NOT STARTED | Task T7. |
| B6 | Freeze Hermes page | IN PROGRESS | Partial via S9a; rows must agree. Task T8 (founder choice first). |
| B7 | "Not investment advice" line on `/pricing` | NOT STARTED | Checkout suspension is a founder decision. Task T9. |

---

## Phase 0A — Re-Gate Honestly

| # | Task | Status | Notes |
|---|---|---|---|
| A1 | Fix STATUS link to master plan | MERGED-NOT-DEPLOYED (docs-only) | Fixed in `662559a`. |
| A2 | Rewrite `phase_0a_baseline_report.md` | NOT STARTED | Memo says PASS over a partial table; dated 2026-09-05. Task T10. |
| A3 | Rewrite `phase_0b_stop_the_bleed.md` | NOT STARTED | Memo says "complete and deployed"; nothing is deployed. Task T10. |
| A4 | `scripts/verify/probe_universe.py` 50+50 probe | NOT STARTED | Task T11. |
| A5 | Docs match the live stack | NOT STARTED | Task T11. |

Phase 0A overall: CONDITIONAL (India names/prices not fresh live; A2–A5 not started).

---

## Verify Phase 0 — Demand Validation

| # | Task | Status | Notes |
|---|---|---|---|
| V0 | `scripts/verify/check_note.py` | NOT STARTED | Only after 0-SEC and 0B are VERIFIED-LIVE. Task T15. |
| V1 | Run V0 on 3 sample public notes | NOT STARTED | Satyam supplies notes. |
| V2 | B2B offer + pilot description | IN PROGRESS | Drafted too early (`107691b`); leave alone. |
| V3 | `docs/verify/interviews.csv` | IN PROGRESS | Header only. Rows are never invented. |

---

## Day-30 Gate

| Metric | Target | Current (2026-10-18) |
|---|---|---|
| Customer-discovery interviews | 15+ | 0 |
| Pilots running | 3+ | 0 |
| Paying customers ≥$49/mo | 1+ | 0 |

**Decision:** Not reached.

---

## Founder blockers (Satyam)

1. BLOCKED (founder: Render deploy) — find why `autoDeploy: yes` has not shipped master since before 13 Oct; ship after T1 CI is green; confirm Vercel.
2. BLOCKED (founder: key rotation) — treat key material in history (chiefly the `9a8fd6d` dump) as real until confirmed; rotate; decide on history rewrite.
3. BLOCKED (founder: Hermes and voice) — remove or archive `/hermes`; guest voice pause (F-22).
4. BLOCKED (founder: checkout) — suspend B2C checkout or not; approve disclaimer wording.
5. BLOCKED (founder: employer contract and JV IP terms).
6. BLOCKED (founder: patent attorney; complete spec due 2027-07-07).
7. BLOCKED (founder: LinkedIn claim scrub).
8. BLOCKED (founder: customer discovery, 0/15).
