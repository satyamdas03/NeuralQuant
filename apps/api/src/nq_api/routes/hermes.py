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

_CACHE_TTL = 5.0
_cache: dict[str, tuple[float, dict]] = {}


def _upstream() -> tuple[str, dict]:
    base = os.environ.get("HERMES_API_URL", "").rstrip("/")
    secret = os.environ.get("HERMES_API_SECRET", "")
    if not base or not secret:
        raise HTTPException(503, "Hermes integration not configured")
    return base, {"X-Hermes-Secret": secret}


async def _proxy_get(path: str, params: dict | None = None) -> dict:
    cache_key = f"{path}?{sorted((params or {}).items())}"
    now = time.time()
    hit = _cache.get(cache_key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    base, headers = _upstream()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            r = await client.get(f"{base}{path}", headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Hermes upstream error: {e.response.status_code}")
    except httpx.HTTPError as e:
        # Agent down or cold — serve last cached payload when we have one
        if hit:
            log.warning("Hermes upstream unreachable (%s) — serving stale cache for %s", e, path)
            return hit[1]
        raise HTTPException(503, "Hermes agent unreachable")
    _cache[cache_key] = (now, data)
    return data


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
                    if r.status_code != 200:
                        yield f'data: {{"line": "[proxy] upstream returned {r.status_code}"}}\n\n'
                        return
                    async for chunk in r.aiter_bytes():
                        yield chunk
        except httpx.HTTPError:
            yield 'data: {"line": "[proxy] hermes agent unreachable - stream closed"}\n\n'

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
