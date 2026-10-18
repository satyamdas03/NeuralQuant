"""India quote freshness and the single quote resolver for card + meta (F-01, F-14).

F-01: Indian stock pages served a weeks-old stock_snapshot price with
stale=false because the API trusted the stored flag (and later used a 35-minute
wall-clock threshold while still serving the price).

F-14: the stock card (GET /stocks/{t}) and the meta panel (GET /stocks/{t}/meta)
built name, price, market cap and P/E from different rows, so they disagreed.

Rules:
- An IN quote is stale when more than IN_STALE_WEEKDAY_HOURS weekday hours
  (Mon-Fri, IST) have passed since the snapshot's cached_at. 36 weekday hours
  covers one NSE session plus a weekend; exchange holidays are not modelled,
  so a long holiday weekend can flag a quote stale early (fails closed).
- Missing or unparsable cached_at counts as stale. A stored stale=false never wins.
- A stale quote carries no numeric price or change_pct.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

IN_STALE_WEEKDAY_HOURS = 36
QUOTE_OK = "ok"
QUOTE_STALE = "quote_stale"

# IST has no DST, so a fixed offset is exact and avoids a tzdata dependency.
_IST = timezone(timedelta(hours=5, minutes=30))


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def weekday_hours_between(start: datetime, end: datetime) -> float:
    """Hours between start and end that fall on Mon-Fri in IST."""
    if end <= start:
        return 0.0
    cur = start.astimezone(_IST)
    end = end.astimezone(_IST)
    total = timedelta(0)
    while cur < end:
        next_midnight = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seg_end = min(next_midnight, end)
        if cur.weekday() < 5:
            total += seg_end - cur
        cur = seg_end
    return total.total_seconds() / 3600.0


def in_quote_is_stale(cached_at: Any, now: datetime | None = None) -> bool:
    ts = _parse_ts(cached_at)
    if ts is None:
        return True
    now = now or datetime.now(timezone.utc)
    return weekday_hours_between(ts, now) > IN_STALE_WEEKDAY_HOURS


def _real_name(ticker: str, candidate: Any) -> str | None:
    if not candidate:
        return None
    bare = str(ticker).split(".")[0].upper()
    s = str(candidate)
    if s.split(".")[0].upper() in {bare, ""} or s.lower() == "nan":
        return None
    return s


def _positive(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f <= 0:  # NaN or non-positive sentinel
        return None
    return f


def resolve_in_quote(
    ticker: str,
    snap: dict | None,
    score_row: dict | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve the displayed IN quote fields once, for both card and meta.

    Snapshot fields win; score_cache fills name / market cap / P/E gaps.
    """
    from nq_api.score_builder import _resolve_display_name

    snap = snap or {}
    score_row = score_row or {}
    cached_at = snap.get("cached_at")
    stale = in_quote_is_stale(cached_at, now)

    name = (
        _real_name(ticker, snap.get("company_name"))
        or _real_name(ticker, score_row.get("long_name"))
        or _resolve_display_name(ticker, "IN", None)
    )
    mcap = _positive(snap.get("market_cap")) or _positive(score_row.get("market_cap"))
    pe = _positive(snap.get("pe_ttm")) or _positive(score_row.get("pe_ttm"))
    price = None if stale else _positive(snap.get("price"))
    change = None
    if not stale and snap.get("change_pct") is not None:
        try:
            change = round(float(snap["change_pct"]), 2)
        except (TypeError, ValueError):
            change = None

    return {
        "name": name,
        "current_price": round(price, 2) if price is not None else None,
        "change_pct": change,
        "market_cap": mcap,
        "pe_ttm": round(pe, 1) if pe is not None else None,
        "cached_at": cached_at,
        "stale": stale,
        "quote_status": QUOTE_STALE if stale else QUOTE_OK,
    }
