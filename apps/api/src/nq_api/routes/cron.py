"""Cron-triggered background jobs — replaces GitHub Actions nightly workflows.

Endpoints:
  POST /cron/nightly-score?market=US|IN|BOTH  — rebuild score_cache
  POST /cron/quantfactor-sync                  — sync Excel → quantfactor_universe
  POST /cron/market-refresh                    — refresh market data
  POST /cron/anjali?market=US|IN|BOTH          — disabled (superseded by quantfactor_sync)

In-process scheduler also runs:
  - Market refresh: every 30 min during market hours
  - US scores:      02:00 UTC
  - IN scores:      02:30 UTC
  - QuantFactor sync: 03:00 UTC (auto-downloads Excel from GitHub raw URLs)

All endpoints require CRON_SECRET header to prevent unauthorized triggers.
Jobs run in background threads — endpoints return immediately with status.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["cron"])

CRON_SECRET = os.environ.get("CRON_SECRET", "")

# ── Lock to prevent concurrent runs ──────────────────────────────────────────────
_score_lock = threading.Lock()
_anjali_lock = threading.Lock()

# Track last run results for status polling
_score_last_result: dict = {}
_anjali_last_result: dict = {}


def _verify_secret(authorization: str | None):
    if not CRON_SECRET:
        return  # No secret configured — allow all (dev mode)
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.replace("Bearer ", "").strip()
    if token != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid cron secret")


# ── Nightly Score ───────────────────────────────────────────────────────────────

def _run_nightly_score(market: str) -> dict:
    """Run score_cache rebuild synchronously (in a thread)."""
    from nq_api.jobs.nightly_score import run_market, warm_stock_meta

    results = {"market": market, "rows": 0, "meta": 0, "started": datetime.now(timezone.utc).isoformat()}
    try:
        if market in ("US", "BOTH"):
            results["rows"] += run_market("US")
        if market in ("IN", "BOTH"):
            results["rows"] += run_market("IN")
        # Warm stock_meta (skip on Render to avoid yfinance timeouts)
        if not os.environ.get("RENDER"):
            if market in ("US", "BOTH"):
                results["meta"] += warm_stock_meta("US")
            if market in ("IN", "BOTH"):
                results["meta"] += warm_stock_meta("IN")
    except Exception as exc:
        log.exception("Nightly score failed for %s: %s", market, exc)
        results["error"] = str(exc)
    results["completed"] = datetime.now(timezone.utc).isoformat()
    return results


def _run_score_bg(market: str):
    """Background thread wrapper for nightly score."""
    global _score_last_result
    try:
        log.info("[cron] Starting nightly score rebuild for %s", market)
        result = _run_nightly_score(market)
        _score_last_result = result
        log.info("[cron] Completed nightly score rebuild for %s: %s rows", market, result.get("rows", 0))
    except Exception:
        log.exception("[cron] Nightly score failed for %s", market)
        _score_last_result = {"market": market, "error": "unexpected failure", "completed": datetime.now(timezone.utc).isoformat()}
    finally:
        _score_lock.release()


@router.post("/nightly-score")
def cron_nightly_score(
    market: str = Query("BOTH", pattern="^(US|IN|BOTH)$"),
    authorization: str | None = Header(None),
):
    """Trigger score_cache rebuild. Protected by CRON_SECRET.
    Runs in background thread — returns immediately."""
    _verify_secret(authorization)
    if not _score_lock.acquire(blocking=False):
        return {"status": "already_running", "market": market, "message": "Score rebuild is already running. Use GET /cron/nightly-score/status to check progress."}
    threading.Thread(target=_run_score_bg, args=(market,), daemon=False).start()
    return {"status": "started", "market": market, "message": "Score rebuild started in background. Use GET /cron/nightly-score/status to check progress."}


@router.get("/nightly-score/status")
def cron_nightly_score_status(authorization: str | None = Header(None)):
    """Check status of last nightly score run."""
    _verify_secret(authorization)
    is_running = _score_lock.locked()
    return {"running": is_running, "last_result": _score_last_result}


# ── QuantFactor Engine Enrichment ───────────────────────────────────────────────

def _run_anjali(market: str) -> dict:
    """QuantFactor enrichment — DISABLED (superseded by quantfactor_sync).

    The old yfinance collector wrote to anjali_enrichment, which migration 025
    replaced with quantfactor_universe (fed by the Excel path in
    quantfactor_sync.py). The yfinance collector is redundant and broken on
    Render (yfinance skipped on cloud IPs → 0 rows), so it's a no-op now.
    """
    log.info("[cron] QuantFactor enrichment disabled — superseded by quantfactor_sync (quantfactor_universe)")
    return {
        "market": market,
        "disabled": True,
        "reason": "superseded by quantfactor_sync",
        "total": 0,
        "completed": datetime.now(timezone.utc).isoformat(),
    }


def _run_anjali_bg():
    """Background thread wrapper for QuantFactor enrichment."""
    global _anjali_last_result
    try:
        log.info("[cron] Starting QuantFactor enrichment rebuild")
        result = _run_anjali("BOTH")
        _anjali_last_result = result
        log.info("[cron] Completed QuantFactor enrichment rebuild: %s rows", result.get("total", 0))
    except Exception:
        log.exception("[cron] QuantFactor enrichment failed")
        _anjali_last_result = {"error": "unexpected failure", "completed": datetime.now(timezone.utc).isoformat()}
    finally:
        _anjali_lock.release()


@router.post("/anjali")
def cron_anjali(
    market: str = Query("BOTH", pattern="^(US|IN|BOTH)$"),
    authorization: str | None = Header(None),
):
    """Trigger QuantFactor enrichment rebuild. Protected by CRON_SECRET.
    Runs in background thread — returns immediately."""
    _verify_secret(authorization)
    if not _anjali_lock.acquire(blocking=False):
        return {"status": "already_running", "market": market, "message": "QuantFactor refresh is already running. Use GET /cron/anjali/status to check progress."}
    mkt = market
    threading.Thread(target=lambda: (_run_anjali_bg_wrap(mkt)), daemon=True).start()
    return {"status": "started", "market": market, "message": "QuantFactor refresh started in background. Use GET /cron/anjali/status to check progress."}


def _run_anjali_bg_wrap(market: str):
    """Background thread wrapper for QuantFactor — acquires lock, runs, releases."""
    global _anjali_last_result
    try:
        log.info("[cron] Starting QuantFactor enrichment for %s", market)
        result = _run_anjali(market)
        _anjali_last_result = result
        log.info("[cron] Completed QuantFactor enrichment for %s", market)
    except Exception:
        log.exception("[cron] QuantFactor enrichment failed for %s", market)
        _anjali_last_result = {"market": market, "error": "unexpected failure", "completed": datetime.now(timezone.utc).isoformat()}
    finally:
        _anjali_lock.release()


@router.get("/anjali/status")
def cron_anjali_status(authorization: str | None = Header(None)):
    """Check status of last QuantFactor enrichment run."""
    _verify_secret(authorization)
    is_running = _anjali_lock.locked()
    return {"running": is_running, "last_result": _anjali_last_result}


# ── Market Refresh (stock_snapshot) ─────────────────────────────────────────────

_market_refresh_lock = threading.Lock()
_market_refresh_last_result: dict = {}


def _run_market_refresh_bg(market_filter: str | None):
    """Background thread wrapper for market_refresh."""
    global _market_refresh_last_result
    try:
        log.info("[cron] Starting market refresh (market_filter=%s)", market_filter)
        from nq_api.jobs.market_refresh import run_market_refresh
        result = run_market_refresh(market_filter=market_filter)
        _market_refresh_last_result = result
        log.info("[cron] Market refresh complete: %s", result)
    except Exception:
        log.exception("[cron] Market refresh failed")
        _market_refresh_last_result = {"error": "unexpected failure", "completed": datetime.now(timezone.utc).isoformat()}
    finally:
        _market_refresh_lock.release()


@router.post("/market-refresh")
def cron_market_refresh(
    market: str | None = Query(None, description="Filter to one market (US or IN), or leave blank for all"),
    authorization: str | None = Header(None),
):
    """Trigger stock_snapshot refresh. Protected by CRON_SECRET.
    Runs in background thread — returns immediately."""
    _verify_secret(authorization)
    if not _market_refresh_lock.acquire(blocking=False):
        return {"status": "already_running", "message": "Market refresh is already running. Use GET /cron/market-refresh/status to check progress."}
    mkt = market if market in ("US", "IN") else None
    threading.Thread(target=_run_market_refresh_bg, args=(mkt,), daemon=True).start()
    return {"status": "started", "market": mkt or "ALL", "message": "Market refresh started in background. Use GET /cron/market-refresh/status to check progress."}


@router.get("/market-refresh/status")
def cron_market_refresh_status(authorization: str | None = Header(None)):
    """Check status of last market refresh run."""
    _verify_secret(authorization)
    is_running = _market_refresh_lock.locked()
    return {"running": is_running, "last_result": _market_refresh_last_result}


# ── QuantFactor Sync (quantfactor_universe) ─────────────────────────────────────

_qf_sync_lock = threading.Lock()
_qf_sync_last_result: dict = {}


def _run_qf_sync_bg():
    """Background thread wrapper for quantfactor_sync."""
    global _qf_sync_last_result
    try:
        log.info("[cron] Starting QuantFactor sync")
        from nq_api.jobs.quantfactor_sync import run_quantfactor_sync
        result = run_quantfactor_sync()
        _qf_sync_last_result = result
        log.info("[cron] QuantFactor sync complete: %s", result)
    except Exception:
        log.exception("[cron] QuantFactor sync failed")
        _qf_sync_last_result = {"error": "unexpected failure", "completed": datetime.now(timezone.utc).isoformat()}
    finally:
        _qf_sync_lock.release()


@router.post("/quantfactor-sync")
def cron_quantfactor_sync(authorization: str | None = Header(None)):
    """Trigger quantfactor_universe sync. Protected by CRON_SECRET.
    Runs in background thread — returns immediately."""
    _verify_secret(authorization)
    if not _qf_sync_lock.acquire(blocking=False):
        return {"status": "already_running", "message": "QuantFactor sync is already running. Use GET /cron/quantfactor-sync/status to check progress."}
    threading.Thread(target=_run_qf_sync_bg, daemon=True).start()
    return {"status": "started", "message": "QuantFactor sync started in background. Use GET /cron/quantfactor-sync/status to check progress."}


@router.get("/quantfactor-sync/status")
def cron_quantfactor_sync_status(authorization: str | None = Header(None)):
    """Check status of last QuantFactor sync run."""
    _verify_secret(authorization)
    is_running = _qf_sync_lock.locked()
    return {"running": is_running, "last_result": _qf_sync_last_result}


# ── Onboarding Email Scheduler ───────────────────────────────────────────────────
# NOTE: Email functionality has been removed. Onboarding emails are disabled.

_EMAIL_WINDOWS = []


def _run_onboarding_emails():
    """Disabled — onboarding emails removed."""
    log.info("[onboarding-emails] Skipped (email functionality disabled)")


def _run_market_wrap_broadcast(market: str):
    """Disabled — market wrap email broadcasts removed."""
    log.info("[market-wrap] Skipped %s broadcast (email functionality disabled)", market)


# ── In-process Scheduler ───────────────────────────────────────────────────────

_SCHEDULED_JOBS_STARTED = False
_last_market_refresh: float = 0  # epoch timestamp of last market_refresh run
_MARKET_REFRESH_INTERVAL = 1800  # 30 minutes


async def start_scheduled_jobs():
    """Start in-process cron scheduler for nightly + periodic jobs.

    Scheduled jobs:
      - Market refresh:  every 30 min during market hours (09:25–20:05 UTC for US+IN)
      - US scores:       02:00 UTC
      - IN scores:       02:30 UTC
      - QuantFactor sync: 03:00 UTC (syncs Excel data → quantfactor_universe)
      - Anjali:          20:30 UTC (QuantFactor Engine enrichment)

    Uses asyncio loop + threading so it doesn't block API requests.
    Only starts once even if lifespan is called multiple times.
    """
    global _SCHEDULED_JOBS_STARTED
    if _SCHEDULED_JOBS_STARTED:
        return
    _SCHEDULED_JOBS_STARTED = True

    log.info("[scheduler] Starting in-process cron scheduler (includes market_refresh every 30min)")

    # Cold-start guard: if stock_snapshot is empty, kick off a background market
    # refresh immediately. The scheduler otherwise only runs during market hours,
    # so a deploy outside 03:45–20:00 UTC would leave snapshots empty for hours.
    # On Render we only refresh US market (IN is refreshed by the GCP feed), so
    # the guard only needs to check US rows there.
    try:
        from nq_api.cache.snapshot_cache import count_by_market
        on_render = bool(os.environ.get("RENDER"))
        us_empty = count_by_market("US") == 0
        in_empty = count_by_market("IN") == 0
        should_cold_start = (us_empty and in_empty) if not on_render else us_empty
        if should_cold_start:
            log.info("[scheduler] stock_snapshot is empty — triggering cold-start market refresh")
            if _market_refresh_lock.acquire(blocking=False):
                _last_market_refresh = time.time()
                # On Render this will auto-restrict to US inside run_market_refresh.
                threading.Thread(target=_run_market_refresh_bg, args=(None,), daemon=True).start()
            else:
                log.info("[scheduler] Market refresh already running, skipping cold-start kick")
    except Exception:
        log.exception("[scheduler] Cold-start snapshot check failed")

    # Simple scheduler: check every 60s if it's time to run a job
    async def _scheduler_loop():
        global _last_market_refresh
        _ran_us_today = ""
        _ran_in_today = ""
        _ran_anjali_today = ""
        _ran_qf_sync_today = ""

        while True:
            try:
                now = datetime.now(timezone.utc)
                today = now.strftime("%Y-%m-%d")

                # ── Market refresh: every 30 min during market hours ────────────
                # US market: 09:30–16:00 ET = 13:30–20:00 UTC
                # IN market: 09:15–15:30 IST = 03:45–10:00 UTC
                # Combined window: 03:45–20:00 UTC (covers both markets)
                in_trading_window = (3 <= now.hour < 20) or (now.hour == 20 and now.minute == 0)
                if in_trading_window:
                    elapsed_since_refresh = time.time() - _last_market_refresh
                    if elapsed_since_refresh >= _MARKET_REFRESH_INTERVAL:
                        if _market_refresh_lock.acquire(blocking=False):
                            _last_market_refresh = time.time()
                            log.info("[scheduler] Triggering market refresh at %s (30min interval)", now.isoformat())
                            threading.Thread(target=_run_market_refresh_bg, args=(None,), daemon=True).start()
                        else:
                            log.debug("[scheduler] Market refresh already running, skipping")

                # US scores at 02:00 UTC
                if now.hour == 2 and now.minute < 5 and _ran_us_today != today:
                    _ran_us_today = today
                    log.info("[scheduler] Triggering US nightly score at %s", now.isoformat())
                    if _score_lock.acquire(blocking=False):
                        threading.Thread(target=_run_score_bg, args=("US",), daemon=True).start()
                    else:
                        log.warning("[scheduler] US score already running, skipping")

                # IN scores at 02:30 UTC
                if now.hour == 2 and now.minute >= 25 and now.minute < 35 and _ran_in_today != today:
                    _ran_in_today = today
                    log.info("[scheduler] Triggering IN nightly score at %s", now.isoformat())
                    if _score_lock.acquire(blocking=False):
                        threading.Thread(target=_run_score_bg, args=("IN",), daemon=True).start()
                    else:
                        log.warning("[scheduler] IN score already running, skipping")

                # QuantFactor sync at 03:00 UTC (Excel → quantfactor_universe)
                if now.hour == 3 and now.minute < 5 and _ran_qf_sync_today != today:
                    _ran_qf_sync_today = today
                    log.info("[scheduler] Triggering QuantFactor sync at %s", now.isoformat())
                    if _qf_sync_lock.acquire(blocking=False):
                        threading.Thread(target=_run_qf_sync_bg, daemon=True).start()
                    else:
                        log.warning("[scheduler] QuantFactor sync already running, skipping")

                # Anjali at 20:30 UTC (QuantFactor Engine)
                if now.hour == 20 and now.minute >= 25 and now.minute < 35 and _ran_anjali_today != today:
                    _ran_anjali_today = today
                    log.info("[scheduler] Triggering QuantFactor enrichment at %s", now.isoformat())
                    if _anjali_lock.acquire(blocking=False):
                        threading.Thread(target=_run_anjali_bg_wrap, args=("BOTH",), daemon=True).start()
                    else:
                        log.warning("[scheduler] QuantFactor already running, skipping")

            except Exception:
                log.exception("[scheduler] Error in scheduler loop")

            await asyncio.sleep(60)

    asyncio.create_task(_scheduler_loop(), name="cron_scheduler")