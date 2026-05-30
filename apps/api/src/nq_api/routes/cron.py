"""Cron-triggered background jobs — replaces GitHub Actions nightly workflows.

Endpoints:
  POST /cron/nightly-score?market=US|IN|BOTH  — rebuild score_cache
  POST /cron/anjali?market=US|IN|BOTH           — rebuild anjali_enrichment

All endpoints require CRON_SECRET header to prevent unauthorized triggers.
Jobs run in background threads — endpoints return immediately with status.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
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
    threading.Thread(target=_run_score_bg, args=(market,), daemon=True).start()
    return {"status": "started", "market": market, "message": "Score rebuild started in background. Use GET /cron/nightly-score/status to check progress."}


@router.get("/nightly-score/status")
def cron_nightly_score_status(authorization: str | None = Header(None)):
    """Check status of last nightly score run."""
    _verify_secret(authorization)
    is_running = _score_lock.locked()
    return {"running": is_running, "last_result": _score_last_result}


# ── Anjali Enrichment ───────────────────────────────────────────────────────────

def _run_anjali(market: str) -> dict:
    """Run Anjali enrichment synchronously (in a thread)."""
    import asyncio as _aio
    from nq_api.jobs.nightly_anjali import refresh_anjali_data

    results = {"market": market, "started": datetime.now(timezone.utc).isoformat()}
    try:
        mkt_filter = None if market == "BOTH" else market
        loop = _aio.new_event_loop()
        res = loop.run_until_complete(refresh_anjali_data(market=mkt_filter))
        loop.close()
        results["universes"] = res
        results["total"] = sum(res.values())
    except Exception as exc:
        log.exception("Anjali refresh failed: %s", exc)
        results["error"] = str(exc)
    results["completed"] = datetime.now(timezone.utc).isoformat()
    return results


def _run_anjali_bg():
    """Background thread wrapper for Anjali enrichment."""
    global _anjali_last_result
    try:
        log.info("[cron] Starting Anjali enrichment rebuild")
        result = _run_anjali("BOTH")
        _anjali_last_result = result
        log.info("[cron] Completed Anjali enrichment rebuild: %s rows", result.get("total", 0))
    except Exception:
        log.exception("[cron] Anjali enrichment failed")
        _anjali_last_result = {"error": "unexpected failure", "completed": datetime.now(timezone.utc).isoformat()}
    finally:
        _anjali_lock.release()


@router.post("/anjali")
def cron_anjali(
    market: str = Query("BOTH", pattern="^(US|IN|BOTH)$"),
    authorization: str | None = Header(None),
):
    """Trigger Anjali enrichment rebuild. Protected by CRON_SECRET.
    Runs in background thread — returns immediately."""
    _verify_secret(authorization)
    if not _anjali_lock.acquire(blocking=False):
        return {"status": "already_running", "market": market, "message": "Anjali refresh is already running. Use GET /cron/anjali/status to check progress."}
    mkt = market
    threading.Thread(target=lambda: (_run_anjali_bg_wrap(mkt)), daemon=True).start()
    return {"status": "started", "market": market, "message": "Anjali refresh started in background. Use GET /cron/anjali/status to check progress."}


def _run_anjali_bg_wrap(market: str):
    """Background thread wrapper for Anjali — acquires lock, runs, releases."""
    global _anjali_last_result
    try:
        log.info("[cron] Starting Anjali enrichment for %s", market)
        result = _run_anjali(market)
        _anjali_last_result = result
        log.info("[cron] Completed Anjali enrichment for %s", market)
    except Exception:
        log.exception("[cron] Anjali enrichment failed for %s", market)
        _anjali_last_result = {"market": market, "error": "unexpected failure", "completed": datetime.now(timezone.utc).isoformat()}
    finally:
        _anjali_lock.release()


@router.get("/anjali/status")
def cron_anjali_status(authorization: str | None = Header(None)):
    """Check status of last Anjali enrichment run."""
    _verify_secret(authorization)
    is_running = _anjali_lock.locked()
    return {"running": is_running, "last_result": _anjali_last_result}


# ── In-process Scheduler ───────────────────────────────────────────────────────

_SCHEDULED_JOBS_STARTED = False


async def start_scheduled_jobs():
    """Start in-process cron scheduler for nightly jobs.

    Runs at the same times as the GitHub Actions workflows did:
      - US scores:  02:00 UTC
      - IN scores:  02:30 UTC
      - Anjali:    20:30 UTC

    Uses asyncio loop + threading so it doesn't block API requests.
    Only starts once even if lifespan is called multiple times.
    """
    global _SCHEDULED_JOBS_STARTED
    if _SCHEDULED_JOBS_STARTED:
        return
    _SCHEDULED_JOBS_STARTED = True

    log.info("[scheduler] Starting in-process cron scheduler")

    # Simple scheduler: check every 60s if it's time to run a job
    async def _scheduler_loop():
        _ran_us_today = ""
        _ran_in_today = ""
        _ran_anjali_today = ""

        while True:
            try:
                now = datetime.now(timezone.utc)
                today = now.strftime("%Y-%m-%d")

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

                # Anjali at 20:30 UTC
                if now.hour == 20 and now.minute >= 25 and now.minute < 35 and _ran_anjali_today != today:
                    _ran_anjali_today = today
                    log.info("[scheduler] Triggering Anjali enrichment at %s", now.isoformat())
                    if _anjali_lock.acquire(blocking=False):
                        threading.Thread(target=_run_anjali_bg_wrap, args=("BOTH",), daemon=True).start()
                    else:
                        log.warning("[scheduler] Anjali already running, skipping")

            except Exception:
                log.exception("[scheduler] Error in scheduler loop")

            await asyncio.sleep(60)

    asyncio.create_task(_scheduler_loop(), name="cron_scheduler")