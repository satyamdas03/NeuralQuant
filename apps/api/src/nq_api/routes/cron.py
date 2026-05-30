"""Cron-triggered background jobs — replaces GitHub Actions nightly workflows.

Endpoints:
  POST /cron/nightly-score?market=US|IN|BOTH  — rebuild score_cache
  POST /cron/anjali?market=US|IN|BOTH           — rebuild anjali_enrichment

All endpoints require CRON_SECRET header to prevent unauthorized triggers.

In-process scheduler also runs these automatically at the same times as GHA did:
  - US scores: 02:00 UTC
  - IN scores: 02:30 UTC
  - Anjali: 20:30 UTC
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


@router.post("/nightly-score")
def cron_nightly_score(
    market: str = Query("BOTH", regex="^(US|IN|BOTH)$"),
    authorization: str | None = Header(None),
):
    """Trigger score_cache rebuild. Protected by CRON_SECRET."""
    _verify_secret(authorization)
    if not _score_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Score rebuild already running")
    try:
        return _run_nightly_score(market)
    finally:
        _score_lock.release()


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


@router.post("/anjali")
def cron_anjali(
    market: str = Query("BOTH", regex="^(US|IN|BOTH)$"),
    authorization: str | None = Header(None),
):
    """Trigger Anjali enrichment rebuild. Protected by CRON_SECRET."""
    _verify_secret(authorization)
    if not _anjali_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Anjali refresh already running")
    try:
        return _run_anjali(market)
    finally:
        _anjali_lock.release()


# ── In-process Scheduler ───────────────────────────────────────────────────────

_SCHEDULED_JOBS_STARTED = False


def _run_score_bg(market: str):
    """Background thread wrapper for nightly score."""
    try:
        log.info("[scheduler] Starting nightly score rebuild for %s", market)
        _run_nightly_score(market)
        log.info("[scheduler] Completed nightly score rebuild for %s", market)
    except Exception:
        log.exception("[scheduler] Nightly score failed for %s", market)


def _run_anjali_bg():
    """Background thread wrapper for Anjali enrichment."""
    try:
        log.info("[scheduler] Starting Anjali enrichment rebuild")
        _run_anjali("BOTH")
        log.info("[scheduler] Completed Anjali enrichment rebuild")
    except Exception:
        log.exception("[scheduler] Anjali enrichment failed")


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

    import asyncio as _aio
    from datetime import time as _time

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
                    threading.Thread(target=_run_score_bg, args=("US",), daemon=True).start()

                # IN scores at 02:30 UTC
                if now.hour == 2 and now.minute >= 25 and now.minute < 35 and _ran_in_today != today:
                    _ran_in_today = today
                    log.info("[scheduler] Triggering IN nightly score at %s", now.isoformat())
                    threading.Thread(target=_run_score_bg, args=("IN",), daemon=True).start()

                # Anjali at 20:30 UTC
                if now.hour == 20 and now.minute >= 25 and now.minute < 35 and _ran_anjali_today != today:
                    _ran_anjali_today = today
                    log.info("[scheduler] Triggering Anjali enrichment at %s", now.isoformat())
                    threading.Thread(target=_run_anjali_bg, daemon=True).start()

            except Exception:
                log.exception("[scheduler] Error in scheduler loop")

            await asyncio.sleep(60)

    asyncio.create_task(_scheduler_loop(), name="cron_scheduler")