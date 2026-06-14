"""Security event audit log (roadmap P6).

`record()` emits a structured WARNING and best-effort persists to the
`security_events` Supabase table. It NEVER raises and never meaningfully blocks
the request path: DB writes are throttled per (event_type, ip) so an attacker
cannot amplify load through the audit log itself.

Note: the log-redaction filter (Session 92) scrubs emails from log output, so the
email survives only in the secured DB row — which is the intended split (audit
trail in the locked table, redacted in plaintext logs).
"""
from __future__ import annotations

import logging
import os
import threading
import time

import httpx

log = logging.getLogger("nq_api.security")

_THROTTLE_LOCK = threading.Lock()
_LAST_WRITE: dict[str, float] = {}
_THROTTLE_S = 60.0  # at most one DB write per (event_type, ip) per minute


def _should_persist(key: str) -> bool:
    now = time.monotonic()
    with _THROTTLE_LOCK:
        last = _LAST_WRITE.get(key, 0.0)
        if now - last < _THROTTLE_S:
            return False
        _LAST_WRITE[key] = now
        if len(_LAST_WRITE) > 5_000:
            for k, t in list(_LAST_WRITE.items()):
                if now - t > _THROTTLE_S:
                    _LAST_WRITE.pop(k, None)
        return True


def record(
    event_type: str,
    *,
    severity: str = "warning",
    email: str | None = None,
    ip: str | None = None,
    detail: str | None = None,
) -> None:
    """Log a security-relevant event and best-effort persist it. Never raises."""
    log.warning(
        "security_event type=%s severity=%s email=%s ip=%s detail=%s",
        event_type, severity, email or "-", ip or "-", detail or "-",
    )

    if not _should_persist(f"{event_type}:{ip or email or '-'}"):
        return

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return
    try:
        with httpx.Client(timeout=3) as c:
            c.post(
                f"{url}/rest/v1/security_events",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={
                    "event_type": event_type,
                    "severity": severity,
                    "email": email,
                    "ip": ip,
                    "detail": detail,
                },
            )
    except Exception:
        log.debug("security_events insert failed (non-fatal)", exc_info=True)
