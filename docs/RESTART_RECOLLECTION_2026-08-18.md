# NeuralQuant — Restart Recollection

**Date:** 2026-08-18  
**Project:** NeuralQuant (formerly QuantAlpha) — AI equity research + paper-trading platform  
**Repo:** `C:\Users\point\projects\stockpredictor`  
**Remote:** `satyamdas03/NeuralQuant`  
**Current branch:** `master`

---

## TL;DR — where we are right now

| Item | Value |
|---|---|
| **Git HEAD** | `5770304` — `feat(market): Render skips IN refresh; add OpenBB IN fallback` |
| **API version** | `4.1.3` (`apps/api/src/nq_api/main.py:385`) |
| **Uncommitted work** | `snapshot_cache.py`, `market_refresh.py`, `infra/gcp/README.md` (ticker-normalization + GCP India-feed docs) |
| **New untracked files** | `infra/gcp/india_feed.py`, `infra/gcp/setup_india_feed.sh` |
| **Score cache** | 943 rows (497 IN + 446 US) as of last build |
| **Live backend** | `https://neuralquant.onrender.com` |
| **Frontend** | `https://neuralquant.co` (Vercel) |
| **Hermes trading agent** | GCP Always-Free `e2-micro` VM (`34.10.176.93` ephemeral) |
| **Last full audit** | Session 109b — 15/15 smoke tests green, 2026-08-18 |

**The single thing you were doing when the laptop restarted:** finishing the **India price-feed fix**. Render's outbound IPs are blocked by Yahoo, so the scheduled `market_refresh` could not populate `price`/`change_pct` for Indian tickers. You built an autonomous `india_feed.py` that runs as a cron on the same GCP VM hosting Hermes, fetches NSE prices via yfinance from an unblocked IP, and writes them into the same `stock_snapshot` table. The uncommitted edits on disk are the last pieces of that work.

---

## 1. The current diff — what changed since the last commit

### `apps/api/src/nq_api/cache/snapshot_cache.py`
Added `_normalize_snapshot_ticker()` and applied it to `write_snapshot`, `read_snapshot`, and `read_snapshot_batch`.

- **Why:** `quantfactor_universe` stores Indian tickers as `RELIANCE.NS`, but `stocks.py`, `nightly_score.py`, `portfolio.py`, and `market_refresh.py` historically keyed `stock_snapshot` by bare ticker (`RELIANCE`). The mismatch caused IN snapshot reads to miss rows that had actually been written.
- **Fix:** normalize `.NS`/`.BO` to bare form on both write and read when `market == "IN"`.

### `apps/api/src/nq_api/jobs/market_refresh.py`
In `_build_snapshot_rows`, FMP/yfinance result dicts are now keyed by **bare** ticker via `_bare(t)` instead of the raw `meta["ticker"]` (which may be suffixed). This makes the merge between `tickers_meta`, `fmp_data`, and `yf_data` line up correctly after the snapshot-cache normalization change.

### `infra/gcp/README.md`
Added a new section **"India price feed (autonomous cron)"** documenting:
- Render's yfinance block
- the GCP feeder as the primary IN source
- setup commands (`setup_india_feed.sh`, `.env`, manual run)
- crontab window: every 15 min, 03:45–10:00 UTC, Mon–Fri
- US-only refresh on Render; IN owned by the GCP feeder

### New: `infra/gcp/india_feed.py`
A ~230-line standalone feeder.
- Loads all `market=IN` tickers from `quantfactor_universe` via `_supabase_rest`.
- Fetches prices in chunks of 50 using `yf.download(period="5d", auto_adjust=True)` and computes `change_pct` from the last two closes.
- Merges static metadata (sector, beta, P/E) from `quantfactor_universe`.
- Upserts rows into `stock_snapshot` via `write_snapshot()` with `source="gcp_yfinance"`, `currency="INR"`.
- Includes CLI `--limit` flag for testing.

### New: `infra/gcp/setup_india_feed.sh`
One-time root setup script:
- installs `git`, `python3-venv`, `cron`
- clones (or pulls) the repo into `/opt/neuralquant`
- creates a venv and installs lightweight deps: `yfinance`, `curl_cffi`, `pandas`, `numpy`, `httpx`, `python-dotenv`
- writes `.env` template for Supabase credentials
- installs a crontab entry: `*/15 4-10 * * 1-5`

---

## 2. Recent session chronology (last 8 sessions)

### Session 106 — Hermes → GCP + quantastra deploy fix
- Migrated Hermes from expired Railway trial to a GCP Always-Free `e2-micro` VM (`us-central1-a`, Ubuntu 24.04, 30 GB standard disk, ephemeral IP `34.10.176.93`).
- Fixed quantastra-agent Render deploy: PyPI 502 fetching latest `hatchling` → pinned `hatchling==1.29.0` in all 4 `pyproject.toml` files.
- Verified all 26 Supabase migrations applied.
- Hermes live: paper mode, strategy v59, `/health` OK.

### Session 107 — US market_cap/name heal + Ask Morgan ticker hint
- Root cause: 446 US score_cache rows had `market_cap=0`/`name=placeholder` because FMP batch failed during a deploy swap and all tickers became `source=fallback`.
- Healed `stock_snapshot` with `run_market_refresh('US')` → 446/446 FMP hits.
- Rebuilt `score_cache` from `quantfactor_universe`.
- Deleted 17 Excel-legend garbage rows from `stock_snapshot` (e.g., "COLOR HIERARCHIES…", "LIGHT GREEN (+0.5)").
- Code: `nightly_score.py` populates `market_cap`, `week52_high/low`, `analyst_target` from snapshot metadata; `enrichment.py` accepts `ticker_hint` for open-ended questions; dashboard hydration fix.
- Verified live: all endpoints 200, Ask Morgan injects data, 76 tests green.

### Session 108 — Split-brain collapse → `quantfactor_universe`
- Collapsed legacy `anjali_enrichment` (0 rows) onto `quantfactor_universe` (943 rows) across QuantAstra tools/context, anjali_context, stock_summary.
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
- **Pending:** manual deploy of `quantastra-agent` Render worker to pick up TTS change; delete Railway service.

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

---

## 3. Architecture snapshot

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

---

## 4. The problem you were solving when the restart happened

**India stocks had no price/change_pct.**

Root cause chain:
1. `market_refresh` uses yfinance for IN fallback after FMP misses.
2. Yahoo blocks Render's outbound IPs, so direct yfinance from nq-api fails.
3. FMP has no Indian coverage.
4. `stock_snapshot` therefore had no `price`/`change_pct` for most IN tickers.
5. Frontend showed "price unavailable" and `change_pct: null` for TCS, RELIANCE, etc.

**Your solution (in progress):**
- Commit `5770304` made the scheduled Render refresh US-only and added an OpenBB safety net for explicit `/cron/market-refresh?market=IN` calls.
- New `infra/gcp/india_feed.py` runs on the unblocked GCP VM and writes IN prices to `stock_snapshot`.
- Uncommitted edits normalize ticker suffixes so the feeder-written rows are readable by the rest of the app.

**Why this matters:** once committed, pushed, and the GCP cron is enabled, `/stocks/TCS.NS?market=IN` (and every other Indian ticker) should show a live price and `change_pct` just like US tickers.

---

## 5. Still-open items and known limitations

### Operational / needs user action
1. **quantastra-agent manual deploy** — Render worker needs a manual deploy to pick up the LiveKit Inference TTS change from Session 109.
2. **Railway cleanup** — delete remaining Railway service `zonal-curiosity` + volume + account if no other paid services.
3. **Key rotation** — explicitly deferred by you; CRON_SECRET and other secrets were pasted in chat.
4. **GCP India feeder setup** — needs `.env` with Supabase credentials installed on the VM and the cron enabled.
5. **FMP key** — still the primary US data source; rotate if needed.

### Data-source limitations
- **IN `change_pct` / price** — about to be solved by the GCP feeder, but until it runs, most IN tickers still show `None`.
- **yfinance fragility** — mitigated by `yf_guard`, FMP primary, Render skip, and now GCP feeder.
- **OpenBB cold start** — Render free-tier sleeps; first Terminal request after idle takes 30–60 s.
- **`/query/v2` deep-dive latency** — multi-agent PARA-DEBATE can exceed 60 s on Render.

### Code / product
- `growth` sub-score is 0.5 for all stocks because `score_cache` lacks a `growth_percentile` column (non-blocking, known since Session 102).
- `/market/indices` returns 404 — endpoint not implemented (noted in Session 109b).
- `/backtest` is an API only; no frontend page (also noted in 109b).

---

## 6. Resume checklist — what to do next

To pick up exactly where you left off:

1. **Commit the India-feed work.**
   ```bash
   git add apps/api/src/nq_api/cache/snapshot_cache.py
   git add apps/api/src/nq_api/jobs/market_refresh.py
   git add infra/gcp/README.md
   git add infra/gcp/india_feed.py
   git add infra/gcp/setup_india_feed.sh
   git commit -m "feat(infra): autonomous GCP India price feeder + snapshot ticker normalization"
   git push origin master
   ```

2. **Deploy / install on the GCP VM.**
   SSH into the Hermes VM and run:
   ```bash
   sudo bash /opt/neuralquant/infra/gcp/setup_india_feed.sh
   sudo nano /opt/neuralquant/apps/api/.env   # add SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
   sudo /opt/neuralquant/venv/bin/python /opt/neuralquant/infra/gcp/india_feed.py --limit 10
   ```

3. **Verify live.**
   ```bash
   curl https://neuralquant.onrender.com/stocks/TCS.NS?market=IN
   curl https://neuralquant.onrender.com/stocks/RELIANCE.NS?market=IN
   ```
   Expect non-null `price` and `change_pct` after the feeder has run once.

4. **Run smoke tests.**
   ```bash
   python scripts/smoke_test.py
   ```
   Target: 15/15 green.

5. **Optional housekeeping.**
   - Manual deploy `quantastra-agent` on Render.
   - Final Railway deletion.
   - Key rotation (when you are ready).

---

## 7. Key gotchas to keep in mind

- **`.NS` normalization is now centralized in `snapshot_cache.py`.** Any future code that reads or writes `stock_snapshot` for IN tickers will get the bare form automatically, but code that builds result dicts (like `market_refresh.py`) must also use `_bare()` when matching against snapshot rows.
- **Render skips IN refresh.** `market_filter=None` on Render now forces `market_filter="US"`. To refresh IN explicitly, call `/cron/market-refresh?market=IN` or rely on the GCP feeder.
- **GCP VM IP is ephemeral.** If the VM is stopped/restarted, `HERMES_API_URL` and any hardcoded IP references must be updated.
- **Auto-deploy caveat.** Render auto-deploy webhook has been unreliable in the past; verify `/health` after each push.
- **Version mismatch.** `apps/api/pyproject.toml` says `2.0.0`, but the live API reports `4.1.3` from `main.py`. Use `main.py` as the source of truth.

---

## 8. Session memory cross-references

Most relevant files (newest first):
- `memory/session109_railway_cleanup_deep_audit.md` — last full audit + `.NS` score-cache fix
- `memory/session109_voice_infra_cleanup.md` — ElevenLabs removal + infra cleanup
- `memory/session108_split_brain_collapse.md` — `quantfactor_universe` collapse
- `memory/session107_e2e_fix_us_mcap_askmorgan.md` — US data heal + Ask Morgan ticker hint
- `memory/session106_gcp_hermes_migration.md` — GCP VM setup + hatchling pin

Reference docs:
- `docs/OPERATIONS.md` — runbook, env vars, services
- `docs/BUG_HISTORY.md` — 126-bug catalog by root-cause class
- `docs/EMERGENCY_SHUTDOWN_RESUME_PLAN.md` — cost breakdown + shutdown/resume steps

---

*This recollection was generated on 2026-08-18 from the current repo state, git history, session memory files, and active code diffs.*
