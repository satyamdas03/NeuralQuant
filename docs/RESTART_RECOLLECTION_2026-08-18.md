# NeuralQuant — Restart Recollection

**Date:** 2026-09-01  
**Project:** NeuralQuant (formerly QuantAlpha) — AI equity research + paper-trading platform  
**Repo:** `C:\Users\point\projects\stockpredictor`  
**Remote:** `satyamdas03/NeuralQuant`  
**Current branch:** `master`

---

## TL;DR — where we are right now

| Item | Value |
|---|---|
| **Git HEAD** | `6e077d9` — `fix(api): remove stale email_sent references and declare ADMIN_EMAILS` |
| **API version** | `4.1.3` (`apps/api/src/nq_api/main.py:385`) |
| **Score cache** | 943 rows (497 IN + 446 US), post-Session 110/110b normalization fixes |
| **Live backend** | `https://neuralquant.onrender.com` |
| **Frontend** | `https://neuralquant.co` (Vercel) |
| **Hermes trading agent** | GCP Always-Free `e2-micro` VM (`34.10.176.93` ephemeral) |
| **Last full audit** | Session 110b — 169 backend tests green, Next.js build clean |

**State:** all previously uncommitted India-feed and ticker-normalization work is now committed and pushed. The GCP India price feeder, snapshot-cache `.NS` normalization, and score-cache composite-scale fixes are in `master`. What remains are operational tasks (deploys, secret rotation, migration application, GCP VM setup) documented in `docs/OPERATOR_RUNBOOK_SESSION_110C.md`.

---

## 1. Recent session chronology (last 8 sessions)

### Session 106 — Hermes → GCP + quantastra deploy fix
- Migrated Hermes from expired Railway trial to a GCP Always-Free `e2-micro` VM (`us-central1-a`, Ubuntu 24.04, 30 GB standard disk, ephemeral IP `34.10.176.93`).
- Fixed quantastra-agent Render deploy: PyPI 502 fetching latest `hatchling` → pinned `hatchling==1.29.0` in all 4 `pyproject.toml` files.
- Verified all 26 Supabase migrations applied.
- Hermes live: paper mode, strategy v59, `/health` OK.

### Session 107 — US market_cap/name heal + Ask Morgan ticker hint
- Root cause: 446 US `score_cache` rows had `market_cap=0`/`name=placeholder` because FMP batch failed during a deploy swap and all tickers became `source=fallback`.
- Healed `stock_snapshot` with `run_market_refresh('US')` → 446/446 FMP hits.
- Rebuilt `score_cache` from `quantfactor_universe`.
- Deleted 17 Excel-legend garbage rows from `stock_snapshot` (e.g., "COLOR HIERARCHIES…", "LIGHT GREEN (+0.5)").
- Code: `nightly_score.py` populates `market_cap`, `week52_high/low`, `analyst_target` from snapshot metadata; `enrichment.py` accepts `ticker_hint` for open-ended questions; dashboard hydration fix.
- Verified live: all endpoints 200, Ask Morgan injects data, 76 tests green.

### Session 108 — Split-brain collapse → `quantfactor_universe`
- Collapsed legacy `anjali_enrichment` (0 rows) onto `quantfactor_universe` (943 rows) across QuantAstra tools/context, anjali_context, `stock_summary`.
- Renamed `composite_anjali_score` → `composite_score`.
- Hardened `nightly_score.py`: read `quantfactor_universe` **before** deleting `score_cache` (previously a transient empty read left the cache at 0 rows).
- Fixed ingestor `fetched_at` → `refreshed_at` drift; GHA `--india-csv` → `--india-excel`; `_run_anjali` no-op.
- Verified: NVDA composite=7.0, TCS.NS?market=IN composite=-6.0, 76 tests green.

### Session 109 — ElevenLabs → LiveKit Inference + infra cleanup
- Removed ElevenLabs/Sarvam TTS; voice now uses `livekit.agents.inference.TTS` (cartesia/sonic-3.5, voices `Daniela`/`Jacqueline`).
- Deleted redundant GHA workflows `market-refresh.yml` and `quantfactor-sync.yml` (in-process scheduler on Render replaces them).
- Deleted stale `infra/oracle-cloud/` kit.
- Cleaned Railway→GCP Hermes references across `hermes.py`, `apps/web/src/app/hermes/page.tsx`, `.env.example`, `docs/OPERATIONS.md`, `README.md`.
- 158 tests green, `/hermes/health` OK.
- **Pending:** manual deploy of `quantastra-agent` Render worker to pick up TTS change.

### Session 109b — Railway cleanup + deep prod audit
- Confirmed Railway Hermes deleted.
- Fixed `/screener/preview?market=BOTH` empty results and `/screener?market=BOTH` HTTP 500 by merging US+IN in `screener.py` and adding `BOTH`/`GLOBAL` to route schemas.
- Fixed null `change_pct` on `/stocks/{ticker}` by backfilling from `stock_snapshot` and direct yfinance gap-fill.
- Fixed broken `/stocks/{ticker}/stream` SSE coroutine.
- Fixed empty `stock_snapshot` after off-market-hour deploys: in-process scheduler now runs a cold-start `market_refresh` if both US and IN counts are zero.
- Fixed `snapshot_cache.count_by_market()` to use PostgREST `count()` aggregation.
- Removed stale Resend reference from privacy page.
- Bumped to v4.1.3, added focused tests for BOTH/GLOBAL merge.
- **Smoke: 15/15 PASS.**
- Follow-up commit `6516904` fixed `nightly_score.py` stripping `.NS` from IN tickers when writing `score_cache`, so `/stocks/TCS.NS?market=IN` and `/stocks/RELIANCE.NS?market=IN` now return real composite scores (5/10).

### Session 110 — 100% health sweep
- Refreshed README/OPERATIONS to v4.1.3, GCP/LiveKit Inference, no email.
- Enriched `infra/gcp/india_feed.py` with volume, 52-week range, company name, and market_cap.
- Fixed scheduler cold-start herd behavior.
- Added `growth_percentile`/`score_1_10`/regime to the `score_cache` default column set; added `GET /market/indices`.
- Extended `BUG_HISTORY` through Session 109.
- **169 backend tests passed, Next.js build clean.**

### Session 110b — Residual score-scale + quality/growth fix
- Fixed four remaining `score_cache.composite_score` consumers that were not using `normalize_cache_composite`: `score_builder`, `analyst`, `dart_router`, `enrichment`.
- Gave `quality_percentile` a distinct synthetic proxy (`0.6*growth + 0.4*risk`) in `nightly_score.py` instead of duplicating `growth_percentile`.
- Isolated `test_screener_filters_by_min_score` from the live DB cache.
- Commit `67e1c68` pushed to `master`.
- **169 backend tests passed, Next.js build clean.**

### Session 110c — Email schema cleanup + ADMIN_EMAILS declaration
- Removed remaining stale `email_sent` references in `session.py` so migration `028_remove_email_schema.sql` is safe to apply.
- Declared `ADMIN_EMAILS` requirement in code/env docs.
- Commit `6e077d9` pushed to `master`.
- **Next:** follow `docs/OPERATOR_RUNBOOK_SESSION_110C.md` for non-code operational tasks.

---

## 2. Architecture snapshot

```
Frontend (Next.js)  →  Vercel (hobby)  →  neuralquant.co
Backend (FastAPI)   →  Render Pro     →  neuralquant.onrender.com  (v4.1.3)
OpenBB proxy        →  Render Standard →  nq-openbb
Voice worker        →  Render Standard →  quantastra-agent (LiveKit)
Trading daemon      →  GCP e2-micro   →  Hermes (paper mode v59)
India price feeder  →  GCP e2-micro   →  yfinance → stock_snapshot
Database            →  Supabase free  →  public.* tables
Market data         →  FMP Premium ($49/mo) primary; yfinance fallback
Cron/refresh        →  In-process scheduler on nq-api (no GHA)
```

### Key tables
- `quantfactor_universe` — canonical 943-row universe (497 IN + 446 US), replaces legacy `anjali_enrichment`.
- `stock_snapshot` — live prices + fundamentals, refreshed every 30 min.
- `score_cache` — nightly composite scores + factor percentiles; rebuilt by `nightly_score.py`.

### Important env vars
- `RENDER=true` — causes `market_refresh` to skip IN and refresh US only.
- `HERMES_API_URL`, `HERMES_API_SECRET` — Render nq-api → GCP Hermes proxy.
- `CRON_SECRET` — required for `POST /cron/*` triggers.
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — used by both Render and GCP feeder.
- `ADMIN_EMAILS` — required for analytics dashboard access (e.g., `satyamdas03@gmail.com`).

---

## 3. The problem you were solving when the restart happened

**India stocks had no price/change_pct.**

Root cause chain:
1. `market_refresh` uses yfinance for IN fallback after FMP misses.
2. Yahoo blocks Render's outbound IPs, so direct yfinance from nq-api fails.
3. FMP has no Indian coverage.
4. `stock_snapshot` therefore had no `price`/`change_pct` for most IN tickers.
5. Frontend showed "price unavailable" and `change_pct: null` for TCS, RELIANCE, etc.

**Solution (now committed and pushed):**
- Commit `5770304` made the scheduled Render refresh US-only and added an OpenBB safety net for explicit `/cron/market-refresh?market=IN` calls.
- Commits `d15461e` and `878c2c6` centralized `.NS`/`.BO` ticker normalization in `snapshot_cache.py` and made the GCP feeder self-contained for VM deployment.
- `infra/gcp/india_feed.py` runs on the unblocked GCP VM and writes IN prices to `stock_snapshot`.
- Final code cleanup in `6e077d9` removed stale email references.

**Why this matters:** once the GCP VM has its `.env` and cron enabled, `/stocks/TCS.NS?market=IN` (and every other Indian ticker) should show a live price and `change_pct` just like US tickers.

---

## 4. Still-open items and known limitations

All remaining work is operational/non-code. Follow `docs/OPERATOR_RUNBOOK_SESSION_110C.md` for the exact commands.

### 1. GCP VM — India price feeder
- Gap: `TCS.NS` and `RELIANCE.NS` show `current_price` but `change_pct: null` because Render's IPs are blocked by Yahoo; the GCP VM can reach Yahoo.
- Steps: SSH into the VM, run `sudo bash /opt/neuralquant/infra/gcp/setup_india_feed.sh`, add Supabase credentials to `.env`, test with `--limit 10`, enable cron, watch `/var/log/india_feed.log`.
- Verify: `curl "https://neuralquant.onrender.com/stocks/TCS.NS?market=IN"` returns non-null `change_pct`.

### 2. Render — manual deploy `quantastra-agent`
- Dashboard → `quantastra-agent` → **Manual Deploy → Clear build cache & deploy**.
- Wait ~3 min, then test Veronica from the web UI.

### 3. Railway cleanup
- Delete remaining `zonal-curiosity` service + persistent volume + account if no other paid services remain.
- Pre-check: `curl https://neuralquant.onrender.com/hermes/health` returns `ok`.

### 4. Secret rotation
- **CRON_SECRET**: generate new 48-char secret, update on Render `nq-api`, redeploy.
- **FMP_API_KEY**: revoke old key on fmp.io, generate new key, update Render `nq-api` and local `.env`.
- **HERMES_API_SECRET** (optional): update on both the GCP VM (`/opt/hermes/.env`) and Render `nq-api`, then `sudo systemctl restart hermes`.
- **SMOKE_TEST_SECRET**: production value should be **unset**; only set transiently when running `scripts/smoke_test.py`.

### 5. Render env — set `ADMIN_EMAILS`
- Required for analytics dashboard access: `ADMIN_EMAILS=satyamdas03@gmail.com`.

### 6. Supabase migrations
Apply in order via Supabase Dashboard → SQL Editor:
1. `supabase/migrations/027_security_events.sql`
2. `supabase/migrations/028_remove_email_schema.sql`
3. `supabase/migrations/029_drop_legacy_email_columns.sql`

After applying `026_enable_rls.sql` (if not already applied), run the verification block in `docs/SECURITY_P0_P1_OPERATOR_ACTIONS.md`.

### 7. GCP VM IP drift check
- The VM external IP is ephemeral. If it restarts, update `HERMES_API_URL` on Render.

### Data-source / product limitations
- **OpenBB cold start** — Render free-tier sleeps; first Terminal request after idle takes 30–60 s.
- **`/query/v2` deep-dive latency** — multi-agent PARA-DEBATE can exceed 60 s on Render.
- **`/market/indices`** is implemented but relies on upstream data freshness.
- **`/backtest`** remains API-only; no frontend page.

---

## 5. Resume checklist — what to do next

Do not restart from the old commit/deploy steps below. The canonical next-actions list is now **`docs/OPERATOR_RUNBOOK_SESSION_110C.md`**. Use this checklist only to orient yourself:

1. Open `docs/OPERATOR_RUNBOOK_SESSION_110C.md` and execute sections 1–7 in order.
2. After operational tasks, run local tests: `python -m pytest apps/api/tests packages/ -q --tb=short`.
3. Run production smoke tests only when `SMOKE_TEST_SECRET` is transiently set: `python scripts/smoke_test.py`.
4. Spot-check:
   - `curl https://neuralquant.onrender.com/health`
   - `curl "https://neuralquant.onrender.com/stocks/TCS.NS?market=IN"`
   - `curl https://neuralquant.onrender.com/hermes/health`
5. Target: 15/15 smoke tests green, IN tickers show `change_pct`, Hermes health `ok`.

---

## 6. Key gotchas to keep in mind

- **`.NS` normalization is now centralized in `snapshot_cache.py`.** Any future code that reads or writes `stock_snapshot` for IN tickers will get the bare form automatically, but code that builds result dicts (like `market_refresh.py`) must also use `_bare()` when matching against snapshot rows.
- **Render skips IN refresh.** `market_filter=None` on Render now forces `market_filter="US"`. To refresh IN explicitly, call `/cron/market-refresh?market=IN` or rely on the GCP feeder.
- **GCP VM IP is ephemeral.** If the VM is stopped/restarted, `HERMES_API_URL` and any hardcoded IP references must be updated.
- **Auto-deploy caveat.** Render auto-deploy webhook has been unreliable in the past; verify `/health` after each push.
- **Version mismatch.** `apps/api/pyproject.toml` says `2.0.0`, but the live API reports `4.1.3` from `main.py`. Use `main.py` as the source of truth.
- **Composite-score normalization.** `score_cache.composite_score` is stored on a ±10 quantfactor-style scale; consumers must use `score_builder.normalize_cache_composite()` to convert to the 0–10 presentation scale.

---

## 7. Session memory cross-references

Most relevant files (newest first):
- `memory/session110b_residual_scale_quality_fix.md` — residual composite-scale fix + quality percentile
- `memory/session110_100pct_health_fixes.md` — health sweep, India feeder enrichment, `/market/indices`
- `memory/session109_railway_cleanup_deep_audit.md` — last full audit + `.NS` score-cache fix
- `memory/session109_voice_infra_cleanup.md` — ElevenLabs removal + infra cleanup
- `memory/session108_split_brain_collapse.md` — `quantfactor_universe` collapse
- `memory/session107_e2e_fix_us_mcap_askmorgan.md` — US data heal + Ask Morgan ticker hint
- `memory/session106_gcp_hermes_migration.md` — GCP VM setup + hatchling pin

Reference docs:
- `docs/OPERATOR_RUNBOOK_SESSION_110C.md` — canonical non-code operational next steps
- `docs/OPERATIONS.md` — runbook, env vars, services
- `docs/BUG_HISTORY.md` — 126-bug catalog by root-cause class
- `docs/EMERGENCY_SHUTDOWN_RESUME_PLAN.md` — cost breakdown + shutdown/resume steps

---

*This recollection was updated on 2026-09-01 to reflect Session 110c state (Git HEAD `6e077d9`).*
