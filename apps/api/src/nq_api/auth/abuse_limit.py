"""Lightweight in-process IP abuse rate limiting.

No Redis dependency — an in-memory sliding window keyed by bucket+IP. State is
per-process (not shared across uvicorn workers / Render instances), so this is a
coarse abuse *fuse* for expensive unauthenticated-reachable endpoints (e.g.
LiveKit token issuance, which dispatches a paid agent worker), NOT a precise
quota. Per-user daily quotas live in auth/rate_limit.py.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_LOCK = threading.Lock()
_HITS: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    """Best-effort client IP, honoring the proxy's X-Forwarded-For."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate(key: str, *, limit: int, window_s: float) -> bool:
    """Record a hit for `key`; return True if at/under `limit` in the window."""
    now = time.monotonic()
    cutoff = now - window_s
    with _LOCK:
        dq = _HITS[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        # Opportunistic cleanup so idle keys don't grow unbounded.
        if len(_HITS) > 10_000:
            for k in [k for k, v in _HITS.items() if not v or v[-1] < cutoff]:
                _HITS.pop(k, None)
        return True


def enforce_ip_rate(request: Request, *, bucket: str, limit: int, window_s: float) -> None:
    """Raise 429 if this IP exceeded `limit` requests for `bucket` in `window_s`."""
    ip = client_ip(request)
    if not check_rate(f"{bucket}:{ip}", limit=limit, window_s=window_s):
        from .security_audit import record
        record("rate_limit_block", ip=ip, detail=f"bucket={bucket} limit={limit}/{int(window_s)}s")
        raise HTTPException(
            status_code=429,
            detail="Too many requests — slow down and try again shortly.",
        )
