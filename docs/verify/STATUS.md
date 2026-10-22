# NeuralQuant Verify — Execution Status Tracker

**Current phase:** Phase 0-SEC
**Started:** 2026-10-13
**Last updated:** 2026-10-18 (Sydney, AEDT). T1 CI evidence recorded. Rewritten for task T1; replaces the 2026-10-13 version, which used disallowed values and wrong counts.
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

| Directory | Tests (2026-10-22) |
|---|---|
| apps/api/tests | 150 |
| packages/data | 63 |
| packages/signals | 19 |
| apps/livekit-agent/tests | 17 |
| scripts/backtest/tests | 3 |
| **Full suite** | **252** |

Root `uv run pytest` (testpaths = apps/api/tests + packages) collects 232 (252 − 17 − 3). 232 is **not** the full suite.

History: `53c61a2` 198; after S1–S4 219; `8cdc3e5` 229; T2 API 239; T3 241; market_refresh fix 243; accuracy gate 246 (apps/api/tests 144); Hermes unmount 252 (apps/api/tests 150). The +6 versus 246 is `apps/api/tests/test_hermes_proxy_removed.py` (six parametrized 404 paths). No tests were deleted.

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

**Deploy state (updated 2026-10-18 01:13 UTC):** The public API is the Render web service **`NeuralQuant`** (`srv-d7a5pnchg0os73b9q2ag`, `neuralquant.onrender.com`), not `nq-api`. Its autoDeploy was switched off by Render when it was rolled back to `6e077d9` on 2026-09-03 01:30 UTC (`auto_deploy_disabled`, reason `rollback`), which is why master stopped shipping. On 2026-10-18 00:50 UTC, with Satyam's approval, deploy `dep-dba1fgvavr4c73fppap0` of master `f9f8182` was triggered; live at 00:57 UTC. Satyam re-enables autoDeploy in the dashboard. Workers `nq-trader` and `quantastra-agent` exist on Render with autoDeploy on (they redeployed on 2026-10-18 pushes). Vercel serves the 13 Oct web build.

## INCIDENT (2026-10-18, resolved 06:10 UTC): API restarted without several env vars

- 00:57 UTC deploy of `f9f8182`: Render log `SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set`. The 3 Sep process held them in memory; the service environment no longer had them. `/health` showed `score_cache_rows: null`, AAPL card 503, TCS card score 10.
- 01:17 UTC: `SUPABASE_URL` set on the service via the Render API (non-secret). ~02:27 UTC: Satyam added `SUPABASE_SERVICE_ROLE_KEY` and deployed. 02:35 UTC: `/health` `score_cache_rows: 944`.
- **Still open:** `FMP_API_KEY` is also missing (Render log 02:43:21 UTC `FMP not enabled — skipping batch fetch`). Cold-start market_refresh then wrote 446 US `stock_snapshot` rows with `price: null` and reported success, and score_cache US now has 0/446 rows with `current_price > 0` (live AAPL card `current_price: 0.0`). Other `sync: false` keys in `render.yaml` may also be missing: unverified, because values are never read back.
- 2026-10-18 ~03:50 UTC: Satyam reported restoring `FMP_API_KEY`. Deploy `dep-dba453dg1s2s73an3peg` (live 04:01 UTC) still logs `FMP not enabled — skipping batch fetch` on instance d96b4 at 04:02 UTC; the code reads `os.environ["FMP_API_KEY"]` directly, so the variable is not present on the service under that exact name. Still BLOCKED (founder).
- RESOLVED: Satyam added `FMP_API_KEY` and deployed (`dep-dba60udg1s2s73ato4mg`, live 06:07 UTC). Render log 06:08:05 UTC `[US] snapshot fallback prices: 506 tickers` (was 60). Supabase 06:10 UTC: `stock_snapshot` US 506/506 priced; `score_cache` US 446/446 with `current_price > 0`. Live 06:10 UTC: AAPL card `current_price 343.46`, meta `current_price 343.46`, `cached_at 2026-10-18T06:08:46Z`; MSFT 529.05; NVDA 214.13.
- Code fix VERIFIED-LIVE: PR 18 (`f2866aa`, deploy `dep-dba392rrjlhs738nvkdg`). Render log 2026-10-18 03:01:52 UTC: `market_refresh: skipping 446 of 446 rows with no fresh price (existing snapshots kept)`, summary `success: False, snapshot_rows_written: 0`. US rows already nulled at 02:43 stay null until `FMP_API_KEY` is restored and a refresh runs.
- Open (founder): rotate the Supabase service-role key and FMP key pasted in chat on 2026-10-18; re-enable Render autoDeploy on NeuralQuant.
---

## Phase 0-SEC — Security and Correctness

| # | Task | F-ID | Status | Commit | Evidence / what is missing |
|---|---|---|---|---|---|
| step-0 | Remove audit dump from repo | F-24 | IN PROGRESS | `26bc004` | Gone from tree; blob still in history at `9a8fd6d`. History rewrite is a founder decision. |
| T1 | Suite green in a clean env; ruff installed; CI on push + PR with full suite | F-19, F-03 tests | VERIFIED-LIVE (CI) | `a7650dc` | Green: workflow CI on push of `a7650dc`, https://github.com/satyamdas03/NeuralQuant/actions/runs/39080513854 — Test "229 passed, 22 warnings", Lint "All checks passed!". Red: draft PR satyamdas03/NeuralQuant#14 (branch `ci-red-proof-t1`, one `assert False` test, commit `8a15c3e`), https://github.com/satyamdas03/NeuralQuant/actions/runs/39080913156 — Test failure "1 failed, 229 passed". PR closed and branch deleted 2026-10-18. |
| T1b | Gitleaks `generic-api-key` on test fixture `apps/api/tests/test_cron_smoke_auth.py:30` (flagged on `7f7430a`, run 38332179461) | F-24 hygiene | VERIFIED-LIVE (CI) | `5889833` | Fixture now `CRON_SECRET = "x" * 32` (obvious placeholder, same test meaning). Clean-env full suite 229 passed; ruff exit 0. secret-scan green on `5889833`: https://github.com/satyamdas03/NeuralQuant/actions/runs/39081392706 ; CI green: https://github.com/satyamdas03/NeuralQuant/actions/runs/39081392677 . Caveat: push-triggered gitleaks scans only the pushed commits, so the old value remains in history at `7f7430a`. No history rewrite. |
| S1 | Auth on `POST /live/classify`, `POST /trade/backtest` | F-07, F-08 | CONDITIONAL (non-admin 403 test and pipeline-not-called assertion missing; `/live/execute` open to any signed-in user) | `b48c835` | Live 2026-10-18 01:12 UTC after deploy `dep-dba1fgvavr4c73fppap0` (`f9f8182`): empty unauthenticated `POST /live/classify` → 401, `POST /trade/backtest` → 401 (one probe each). |
| S2 | Unknown ticker → 404 | F-02 | MERGED-NOT-DEPLOYED | `02aa8ce`, `7659da1` | 2026-10-22 (T12 S2, `7659da1`): `GET /stocks/{t}/meta` runs the same universe check as the score route (shared `_require_known_ticker`) and returns 404 `{"detail": "Unknown ticker <t>"}` for US, IN and BOTH; tests assert score and meta messages match. One-row composite tests: 0.0 → `score_1_10` 1 and 0.75 → 10, via `_score_to_1_10` and through the live path. Full suite 283 passed (api 172 → 181). Score route live 2026-10-18 01:12 UTC: `GET /stocks/NOTAREALTICKERXYZ?market=US` → 404 `{"detail": "Unknown ticker NOTAREALTICKERXYZ"}`. `/meta` not probed live: Render autoDeploy is off. |
| S3 | India freshness | F-01, F-14 | CONDITIONAL (API verified live; web badge not checked in a browser; IN feeder stale since 2026-10-05) | `dbdc654` (PR 15) + `bc29e20` (PR 16 web) | Live 2026-10-18 02:43 UTC on deploy `dep-dba30u61egvs7395mjk0` (`8274a06`), Supabase reachable: meta TCS/RELIANCE/INFY/HDFCBANK all `cached_at "2026-09-03T01:04:47Z"`, `stale: true`, `quote_status: "quote_stale"`, `current_price: null`. Card TCS: name "Tata Consultancy Services Ltd.", `current_price: null`, `pe_ttm: 17.4`, `stale: true`, `price_as_of` = snapshot `cached_at`, `last_updated` = score row `computed_at`; matches meta (name, price, P/E, market cap null on both). Web: PR 16 merged; badge is client-rendered and was not checked in a browser. Root problem remains: IN feeder last wrote `stock_snapshot` 2026-10-05 (TCS 2026-09-03), founder/GCP item. |
| S4 | Ask AI blank summary → 502; caps; fence; errors fail closed | F-03, F-04 | MERGED-NOT-DEPLOYED | `d632e33`, `51ad368` | 2026-10-22 (T12 S4, `51ad368`): `/query/v2` timeout → 504 `NQ_QUERY_TIMEOUT`, other errors → 502 `NQ_QUERY_FAILED`, missing key → 503 `NQ_QUERY_UNAVAILABLE`; `/query/v2/stream` sends one SSE error event with the same codes; no `str(exc)` in any body. History and clarification answers are fenced in the single user message; `<`/`>` escaped, tested with a question containing `</user-query>`. Full suite 274 passed (api 158 → 172). Not probed live: Render autoDeploy is off, and `POST /query/v2` is not sent to prod. |
| S5 | CI runs real pytest | F-19 | VERIFIED-LIVE (CI) | `41a4341` + `a7650dc` | Completed by T1; see T1 row for green and red Actions URLs. |
| S6 | Secret scan; rotation | F-24 | BLOCKED (founder: key rotation not confirmed) | `a0b876e` | Report only: `docs/verify/evidence/secret_scan_2026-10-13.md`. |
| S7 | Upgrade runtime deps | F-16 | NOT STARTED | — | Task T13. |
| S8 | `compare_digest`, fail-closed empty `CRON_SECRET`; smoke bypass refused unless `ENVIRONMENT=test` | F-10, F-23 | MERGED-NOT-DEPLOYED | `7f7430a`, `a02b7f8` | Live 2026-10-18 01:12 UTC: `GET /cron/nightly-score/status` (no header) → 401 `{"detail": "missing Bearer token"}` (S8 wording). 2026-10-22 (T12, `a02b7f8`): `_smoke_bypass_ok` returns false unless `ENVIRONMENT=test`; tests cover production + matching `X-Smoke-Secret` → 401 / no user, and test env still authenticates. Full suite 260 passed (api 150 → 158). Not probed live: `X-Smoke-Secret` is never sent to the production host. |
| S9a | Freeze Hermes page | F-06 | VERIFIED-LIVE (superseded by removal, see B6) | `9140812`, `a65f1ad`, `f46a679` | Live 2026-10-18 13:03 UTC: web `/hermes` → 404; API `/hermes/status` and `/hermes/health` → 404. |
| S9b | Guest LiveKit budget / pause voice | F-22 | IN PROGRESS | `f53ab9c` | Constants are never read; guests still dispatched. No test. |
| S9c | Remaining medium/low items | F-09, F-12, F-13, F-15, F-17, F-18, F-21 | NOT STARTED | — | Task T14. |

---

## Phase 0B — Claim and Advice Scrub

| # | Task | Status | Notes |
|---|---|---|---|
| B1 | `/testing/quarterly/public-results` returns no metrics on any branch | VERIFIED-LIVE | `8274a06` (PR 17) | Live 2026-10-18 02:43 UTC with Supabase reachable: 200 `{"quarter": "Q1FY27", "available": false, "summary": null, "pool_breakdown": [], "equity_curve": [], ...}`. Endpoint no longer reads quarterly tables; tests red on old success path. |
| B2 | Remove 87%/Q1FY27 from OG/Twitter and methodology FAQ | VERIFIED-LIVE | `55dc5d0` (PR 19) | Live 2026-10-18 04:03 UTC: `curl https://www.neuralquant.co/ \| grep -c 87%` → 0; `/methodology` → 0 (was 6 each on 2026-10-17). Homepage page metadata also drops "SEBI-compliant". Not gone: "Beat the market" and "Institutional-grade" remain in the root `apps/web/src/app/layout.tsx` metadata and its JSON-LD (live homepage HTML still has "Institutional-grade" in the JSON-LD on 2026-10-22). |
| B3 | Scrub README, ARCHITECTURE, ASSET_INVENTORY, pricing, prospectus | VERIFIED-LIVE (pricing live; docs have no live surface, merged in PR 20) | `c5ff4de` (PR 20 docs), `38e750f` (PR 21 pricing) | Live 2026-10-18 05:40 UTC: `curl https://www.neuralquant.co/pricing` → 0 matches for "proven edge", "genuinely predictive", "outperform"; "Transparent Factors" present. Docs PR: README, ARCHITECTURE, ASSET_INVENTORY, SALE_PROSPECTUS.md, StockEdge prospectus md + regenerated .docx, StockEdge thesis HTML, both generators. Remaining T5 rg hits justified (compliance disclaimer, negation, false positive). |
| B4 | Delete orphaned backtest components and `accuracy()` client | VERIFIED-LIVE (deleted code; web eslint 0 warnings; merged `7b97ec0`, PR 22) | T6 PR: deleted BacktestResultsSection, EquityCurveChart, QuarterlyBreakdownTable, AlphaCounterCard (rg: only imported by each other), `api.accuracy()` + `AccuracyResponse`, unused BarChart3/Zap/MetricCounterCard in methodology. eslint 0 errors, 0 warnings (was 3); build exit 0; web tests 3 passed. `GET /backtest/accuracy` (public, live 200 on 2026-10-18, hit-rate/Sharpe/top-decile returns): gated with `require_admin` and `str(e)` removed (Satyam: "do what is recommended"); 3 tests (2 red on old code). Full suite 246. Live 2026-10-18 08:43 UTC: `GET /backtest/accuracy` → 401 `{"detail": "missing Bearer token"}` (deploy `dep-dba894lg1s2s73b5ko2g`, `fd5e7e5`). |
| B5 | Neutralize BUY/SELL/AVOID labels at UI boundary | CONDITIONAL (UI live incl. methodology pipeline stage; API enums/prompts follow-up open) | 2026-10-22 (Sydney): review 3 found /methodology still rendered "Verdict BUY / HOLD / SELL" in the Data Pipeline Architecture stage 6. T7 remainder PR changes that stage to "Research band / Upper / Middle / Lower" (text only; no API enum, prompt or number change). Local: `rg -n "BUY / HOLD / SELL\|STRONG BUY\|STRONG SELL\|HARD SELL" apps/web/src` hits only `lib/types.ts` (Verdict type), `lib/neutralLabels.ts` and `NeutralLabels.test.tsx`; eslint exit 0, no warnings; vitest 8 passed; build exit 0; built methodology.html 0 matches for "BUY / HOLD / SELL". Merged as PR 27 (`b18fdca`); Vercel production deployment `dpl_Fv8p86HxvKz1M7j8sQGueFdY785M` READY for that SHA (later production deploys from PR 29 and PR 28 also READY). Live 2026-10-22 ~01:40 UTC: GET https://www.neuralquant.co/methodology → 200; occurrences of "BUY / HOLD / SELL" = 0; "Research band\nUpper / Middle / Lower" = 1. Fetched with the Vercel MCP fetcher because this session's egress proxy refused `curl` to www.neuralquant.co (CONNECT 403); a plain `curl -sS https://www.neuralquant.co/methodology \| grep -c 'BUY / HOLD / SELL'` from an open network should be re-pasted here. Earlier: T7 web PR 24 (`135ce2b`). Live 2026-10-18 08:45 UTC: /, /methodology, /pricing → 0 matches for STRONG BUY / STRONG SELL / Strong Buy / Strong Avoid / HARD SELL / INVESTMENT READY; /methodology shows "Upper band". Details: `lib/neutralLabels.ts` maps stored verdicts/consensus/IRS zones to Upper / Middle / Lower band (unknown → Unrated). Wired into VerdictBanner, AgentDebatePanel, IRSZoneBadge, StockSummaryCard, StockMetaBar, ConsensusPanel, DebateProgressPanel, quantfactor page, methodology tables, share page and 3 OG images; "HARD SELL" → "G-SCORE < −4"; /compare IWM answer no longer says "HOLD … wait for $220". Render tests 5 (3 red on old components), web tests 8 passed, eslint 0/0, build 0; built /, /methodology, /pricing HTML 0 advice hits. Not done: API enums/prompts (follow-up PR); `GeopoliticalScanPanel` renders free-text `recommendation` from the API; /compare page quotes competitor answers (founder decision). |
| B6 | Remove Hermes page and public proxy | VERIFIED-LIVE | `a65f1ad` (PR 25 web), `f46a679` (PR 26 API), deploy `dep-dbac3bqjnfac73f5b600` | Satyam 2026-10-18: remove /hermes, keep GCP VM. Live 2026-10-18 13:03 UTC: `https://www.neuralquant.co/hermes` → 404; `https://neuralquant.onrender.com/hermes/status` → 404 (was 200 with live positions); `/hermes/health` → 404; `/health` ok. GCP VM not touched. OPERATIONS.md Render table corrected. F-21 (SSE timeout) moot while the proxy is unmounted. |
| B7 | "Not investment advice" line on `/pricing` | NOT STARTED | Checkout suspension is a founder decision. Task T9. |

---

## Phase 0A — Re-Gate Honestly

| # | Task | Status | Notes |
|---|---|---|---|
| A1 | Fix STATUS link to master plan | MERGED-NOT-DEPLOYED (docs-only) | Fixed in `662559a`. |
| A2 | Rewrite `phase_0a_baseline_report.md` | MERGED-NOT-DEPLOYED (docs-only) | Task T10. Rewritten 2026-10-22: real dates (2026-10-12 pass, 2026-10-22 update), gate CONDITIONAL on stale India prices, A4 and A5. |
| A3 | Rewrite `phase_0b_stop_the_bleed.md` | MERGED-NOT-DEPLOYED (docs-only) | Task T10. Rewritten 2026-10-22: real dates (2026-10-13 pass, 2026-10-22 update); audit-dump line removed; lists only items matched by public curls on 2026-10-22. |
| A4 | `scripts/verify/probe_universe.py` 50+50 probe | NOT STARTED | Task T11. |
| A5 | Docs match the live stack | NOT STARTED | Task T11. |

Phase 0A overall: CONDITIONAL (India prices not fresh live; A4–A5 not started).

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

1. BLOCKED (founder: Render autoDeploy) — the API behaviour on master through `f46a679` is deployed (public curls on 2026-10-22 match T3, T8, S2, S8 wording, accuracy gate). Whether autoDeploy is back on for the `NeuralQuant` service is unconfirmed; confirm in the Render dashboard. Do not treat a future master push as deployed until a curl changes.
2. BLOCKED (founder: key rotation) — treat key material in history (chiefly the `9a8fd6d` dump) as real until confirmed; rotate; decide on history rewrite.
3. BLOCKED (founder: guest voice) — the `/hermes` page and public proxy are removed (B6, VERIFIED-LIVE). Guest voice (F-22) is still open: guests are still dispatched to paid workers; pause or not is a founder decision.
4. BLOCKED (founder: checkout) — suspend B2C checkout or not; approve disclaimer wording.
5. BLOCKED (founder: employer contract and JV IP terms).
6. BLOCKED (founder: patent attorney; complete spec due 2027-07-07).
7. BLOCKED (founder: LinkedIn claim scrub).
8. BLOCKED (founder: customer discovery, 0/15).
