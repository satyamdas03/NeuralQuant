"""Proxy to the Hermes trading agent's state API (Railway).

Same pattern as the OpenBB proxy: the browser only ever talks to nq-api;
the Railway URL and shared secret stay server-side.

Env:
    HERMES_API_URL     e.g. https://zonal-curiosity-production-96f0.up.railway.app
    HERMES_API_SECRET  shared secret, forwarded as X-Hermes-Secret
"""

from __future__ import annotations

import logging
import os
import time

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/hermes", tags=["hermes"])

_DEFAULT_TTL = 5.0
_TTLS: dict[str, float] = {
    "/status": 60.0,
    "/strategy": 60.0,
    "/reflections": 60.0,
    "/trades": 30.0,
}
_cache: dict[str, tuple[float, dict]] = {}

_UPSTREAM_OFFLINE_DETAIL = (
    "Hermes agent is offline. Railway service status: offline. "
    "Last known data may be served from cache."
)


def _cache_ttl(path: str) -> float:
    return _TTLS.get(path, _DEFAULT_TTL)


def _upstream() -> tuple[str, dict]:
    base = os.environ.get("HERMES_API_URL", "").rstrip("/")
    secret = os.environ.get("HERMES_API_SECRET", "")
    if not base or not secret:
        raise HTTPException(503, "Hermes integration not configured")
    return base, {"X-Hermes-Secret": secret}


async def _proxy_get(path: str, params: dict | None = None) -> dict:
    cache_key = f"{path}?{sorted((params or {}).items())}"
    now = time.time()
    ttl = _cache_ttl(path)
    hit = _cache.get(cache_key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    base, headers = _upstream()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            r = await client.get(f"{base}{path}", headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        if hit:
            log.warning(
                "Hermes upstream error (%s) for %s — serving stale cache",
                status_code or e,
                path,
            )
            return hit[1]
        raise HTTPException(503, detail=_UPSTREAM_OFFLINE_DETAIL)
    _cache[cache_key] = (now, data)
    return data


@router.get("/health")
async def health() -> dict:
    """Public liveness probe for the Hermes Railway service."""
    base = os.environ.get("HERMES_API_URL", "").rstrip("/")
    if not base:
        return {
            "status": "offline",
            "upstream_status": None,
            "message": "Hermes integration not configured (HERMES_API_URL missing).",
        }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
            r = await client.get(f"{base}/health")
            if r.is_success:
                return {
                    "status": "ok",
                    "upstream_status": r.status_code,
                    "message": "Hermes agent is reachable.",
                }
            return {
                "status": "offline",
                "upstream_status": r.status_code,
                "message": "Hermes agent returned an error.",
            }
    except httpx.HTTPError as e:
        return {
            "status": "offline",
            "upstream_status": None,
            "message": f"Hermes agent unreachable: {type(e).__name__}.",
        }


@router.get("/status")
async def status() -> dict:
    return await _proxy_get("/status")


@router.get("/trades")
async def trades(n: int = Query(default=200, ge=1, le=2000)) -> dict:
    return await _proxy_get("/trades", {"n": n})


@router.get("/strategy")
async def strategy() -> dict:
    return await _proxy_get("/strategy")


@router.get("/reflections")
async def reflections(n: int = Query(default=50, ge=1, le=500)) -> dict:
    return await _proxy_get("/reflections", {"n": n})


@router.get("/events")
async def events() -> StreamingResponse:
    """SSE passthrough of the live log stream."""
    base, headers = _upstream()

    async def gen():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0)) as client:
                async with client.stream("GET", f"{base}/events", headers=headers) as r:
                    if not r.is_success:
                        yield f'data: {{"line": "Hermes agent is offline. Railway service status: returned {r.status_code}."}}\n\n'
                        return
                    async for chunk in r.aiter_bytes():
                        yield chunk
        except httpx.HTTPError as e:
            yield f'data: {{"line": "Hermes agent is offline. Railway service status: unreachable ({type(e).__name__})."}}\n\n'

    # no-transform: stops intermediaries (incl. Next's compression) from
    # gzip-buffering the stream, which starves EventSource of events.
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
