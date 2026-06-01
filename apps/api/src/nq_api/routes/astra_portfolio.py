"""QuantAstra Portfolio Intelligence — IRS-based selection, sell signals, risk profiling.

Implements the 3 India selection pools, Mining & Metals exclusion,
IRS north-star recommendations, and SEBI disclaimer.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/astra", tags=["astra"])

SEBI_DISCLAIMER = (
    "These recommendations are based on quantitative analysis. "
    "QuantAlpha is a research tool, not a SEBI-registered investment advisor. "
    "Please consult a qualified financial advisor before investing."
)

# Hard thresholds
SELL_G_SCORE_THRESHOLD = -4.0
SELL_RISK_THRESHOLD = -3.5
NEUTRAL_G_SCORE_THRESHOLD = -0.5

MINING_METALS_SECTORS = {"mining", "metals", "mining & metals", "metal", "mining & metal"}


# ── Supabase REST helper ─────────────────────────────────────────────

def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict] | dict | None = None,
) -> list[dict] | dict | None:
    """Direct REST call to Supabase PostgREST."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None

    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    try:
        with httpx.Client(timeout=15) as client:
            if method == "GET":
                r = client.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                r = client.post(endpoint, json=body, headers=headers)
            elif method == "PATCH":
                r = client.patch(endpoint, json=body, params=query or {}, headers=headers)
            elif method == "DELETE":
                r = client.delete(endpoint, params=query or {}, headers=headers)
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as exc:
        logger.warning("Astra REST %s %s failed: %s", method, table, exc)
        return None


def _is_mining_metals(sector: str | None) -> bool:
    """Check if sector is Mining & Metals (always excluded for India)."""
    if not sector:
        return False
    return sector.lower().strip() in MINING_METALS_SECTORS


# ── Selection pools ────────────────────────────────────────────────────

def _fetch_anjali_pool(
    market: str,
    index_groups: list[str] | None = None,
    min_g_score: float | None = None,
    min_risk_score: float | None = None,
    min_irs_pct: float | None = None,
    require_all_growth_positive: bool = False,
    require_holding_positive: bool = False,
    require_fii_quarter_positive: bool = False,
    require_risk_strict: float | None = None,
    limit: int = 50,
) -> list[dict]:
    """Fetch stocks from anjali_enrichment matching selection criteria."""
    query: dict[str, Any] = {
        "select": "ticker,market,index_group,sector,g_score,risk_eff_score,irs_raw,irs_pct,"
                   "growth_score,return_score,valuation_score,risk_score,"
                   "dii_quarter,fii_quarter,future_pe,ttm_peg",
        "market": f"eq.{market}",
        "irs_pct": "not.is.null",
        "order": "irs_pct.desc",
        "limit": str(limit * 3),  # over-fetch, then filter
    }

    if index_groups:
        # PostgREST OR for index_group
        or_parts = ",".join(f"index_group.eq.{ig}" for ig in index_groups)
        query["or"] = f"({or_parts})"

    data = _supabase_rest("anjali_enrichment", "GET", query=query)
    if not data or not isinstance(data, list):
        return []

    results = []
    for row in data:
        # Mining & Metals exclusion
        if _is_mining_metals(row.get("sector")):
            continue

        g = row.get("g_score")
        risk = row.get("risk_score")
        irs = row.get("irs_pct")

        if g is None or risk is None or irs is None:
            continue

        # Min G Score filter
        if min_g_score is not None and g < min_g_score:
            continue

        # Min risk score filter
        risk_threshold = require_risk_strict if require_risk_str is not None else min_risk_score
        if risk_threshold is not None and risk < risk_threshold:
            continue

        # Min IRS% filter
        if min_irs_pct is not None and irs < min_irs_pct:
            continue

        # All growth columns positive (SmallCap/MicroCap requirement)
        if require_all_growth_positive:
            growth = row.get("growth_score")
            if growth is None or growth <= 0:
                continue

        # Holding score positive (DII Quarter or FII Quarter > 0)
        if require_holding_positive:
            dii_q = row.get("dii_quarter")
            fii_q = row.get("fii_quarter")
            holding = (dii_q if dii_q and dii_q > 0 else 0) + (fii_q if fii_q and fii_q > 0 else 0)
            if holding <= 0:
                continue

        # FII Quarter specifically positive
        if require_fii_quarter_positive:
            fii_q = row.get("fii_quarter")
            if fii_q is None or fii_q <= 0:
                continue

        results.append(row)

    return results[:limit]


# ── Endpoints ──────────────────────────────────────────────────────────

@router.post("/recommend")
async def recommend_portfolio(
    risk_profile: Literal["low", "high", "very_high"] = Query(...),
    market: Literal["IN", "US", "BOTH"] = Query("IN"),
    user: User = Depends(get_current_user),
):
    """Recommend 20-25 stock portfolio based on risk profile and IRS scores.

    India selection pools:
    - Low Risk: 100% LM250 (IRS% > 65%, G Score > 0, Risk > 0)
    - High Risk: 50% LM250 + 30% SmallCap + 20% MicroCap
    - Very High Risk: LM250 + SmallCap + MicroCap + Turnaround
    """
    portfolios: dict[str, list] = {}

    if market in ("IN", "BOTH"):
        # Pool A: LM250 Alpha (Large & MidCap)
        lm250 = _fetch_anjali_pool(
            market="IN",
            index_groups=["NSE250", "NIFTY200", "NIFTY100"],
            min_g_score=0,
            min_risk_score=0,
            min_irs_pct=65,
            limit=25,
        )
        portfolios["lm250"] = lm250

        # Pool B: SmallCap High Growth
        smallcap = _fetch_anjali_pool(
            market="IN",
            index_groups=["NSE250"],
            min_g_score=0,
            require_all_growth_positive=True,
            require_holding_positive=True,
            require_fii_quarter_positive=True,
            min_risk_score=0,
            min_irs_pct=50,
            limit=15,
        )
        portfolios["smallcap"] = smallcap

        # Pool C: MicroCap (stricter risk)
        microcap = _fetch_anjali_pool(
            market="IN",
            index_groups=["NSE250"],
            min_g_score=0,
            require_all_growth_positive=True,
            require_holding_positive=True,
            require_fii_quarter_positive=True,
            require_risk_strict=1.0,  # Risk Score > 1.0 for MicroCap
            min_irs_pct=50,
            limit=10,
        )
        portfolios["microcap"] = microcap

        # Pool D: Turnaround (Very High Risk only)
        turnaround = _fetch_anjali_pool(
            market="IN",
            index_groups=["NSE250"],
            require_holding_positive=True,
            require_all_growth_positive=True,
            min_risk_score=0,
            min_irs_pct=40,
            limit=10,
        )
        portfolios["turnaround"] = turnaround

    if market in ("US", "BOTH"):
        us_pool = _fetch_anjali_pool(
            market="US",
            index_groups=["SP500", "SP400", "SP400+SP600"],
            min_g_score=0,
            min_risk_score=0,
            min_irs_pct=65,
            limit=25,
        )
        portfolios["us_sp500"] = us_pool

    # Build allocation based on risk profile
    if risk_profile == "low":
        allocation = {
            "lm250": (20, 25),
            "smallcap": (0, 0),
            "microcap": (0, 0),
            "turnaround": (0, 0),
        }
    elif risk_profile == "high":
        allocation = {
            "lm250": (10, 12),
            "smallcap": (6, 8),
            "microcap": (4, 5),
            "turnaround": (0, 0),
        }
    else:  # very_high
        allocation = {
            "lm250": (8, 10),
            "smallcap": (5, 7),
            "microcap": (3, 4),
            "turnaround": (3, 5),
        }

    recommended = {}
    for pool_name, (min_n, max_n) in allocation.items():
        pool = portfolios.get(pool_name, [])
        n = min(max_n, len(pool))
        recommended[pool_name] = pool[:n]

    # Flatten for total count
    total = sum(len(v) for v in recommended.values())

    # Sell signals — stocks with G Score < -4 or Risk < -3.5
    sell_list = []
    all_stocks = []
    for pool in portfolios.values():
        all_stocks.extend(pool)
    for row in all_stocks:
        g = row.get("g_score")
        r = row.get("risk_score")
        reasons = []
        if g is not None and g < SELL_G_SCORE_THRESHOLD:
            reasons.append(f"G Score {g} < {SELL_G_SCORE_THRESHOLD}")
        if r is not None and r < SELL_RISK_THRESHOLD:
            reasons.append(f"Risk Score {r} < {SELL_RISK_THRESHOLD}")
        if reasons:
            sell_list.append({
                "ticker": row["ticker"],
                "reasons": reasons,
                "g_score": g,
                "risk_score": r,
            })

    # Format recommendation output
    formatted = {}
    for pool_name, stocks in recommended.items():
        formatted[pool_name] = [
            {
                "ticker": s["ticker"],
                "irs_pct": s.get("irs_pct"),
                "g_score": s.get("g_score"),
                "risk_eff_score": s.get("risk_eff_score"),
                "sector": s.get("sector"),
            }
            for s in stocks
        ]

    return {
        "risk_profile": risk_profile,
        "market": market,
        "total_stocks": total,
        "allocation": {k: len(v) for k, v in recommended.items()},
        "recommendations": formatted,
        "sell_signals": sell_list,
        "sebi_disclaimer": SEBI_DISCLAIMER,
    }


@router.post("/assess")
async def assess_portfolio(
    holdings: list[dict],
    user: User = Depends(get_current_user),
):
    """Assess a portfolio's IRS scores. Each holding: {ticker, market, units?, avg_cost?}."""
    results = []
    total_irs = 0.0
    count = 0

    for h in holdings:
        ticker = h.get("ticker", "").upper()
        market = h.get("market", "US")

        # Look up Anjali data
        data = _supabase_rest(
            "anjali_enrichment",
            "GET",
            query={
                "select": "ticker,g_score,risk_eff_score,irs_raw,irs_pct,risk_score,sector",
                "ticker": f"eq.{ticker}",
                "market": f"eq.{market}",
                "limit": "1",
            },
        )
        if data and isinstance(data, list) and len(data) > 0:
            row = data[0]
            irs = row.get("irs_pct")
            g = row.get("g_score")
            risk = row.get("risk_eff_score")

            verdict = "NEUTRAL"
            if g is not None and g < SELL_G_SCORE_THRESHOLD:
                verdict = "SELL"
            elif risk is not None and risk < SELL_RISK_THRESHOLD:
                verdict = "SELL"
            elif g is not None and g < NEUTRAL_G_SCORE_THRESHOLD:
                verdict = "NEUTRAL"
            elif irs is not None and irs > 65:
                verdict = "BUY"
            else:
                verdict = "HOLD"

            results.append({
                "ticker": ticker,
                "market": market,
                "irs_pct": irs,
                "g_score": g,
                "risk_eff_score": risk,
                "sector": row.get("sector"),
                "verdict": verdict,
                "is_mining_metals": _is_mining_metals(row.get("sector")),
            })
            if irs is not None:
                total_irs += irs
                count += 1
        else:
            results.append({
                "ticker": ticker,
                "market": market,
                "irs_pct": None,
                "g_score": None,
                "risk_eff_score": None,
                "sector": None,
                "verdict": "UNKNOWN",
                "is_mining_metals": False,
            })

    avg_irs = round(total_irs / count, 1) if count > 0 else None

    return {
        "holdings": results,
        "total_holdings": len(results),
        "avg_irs_pct": avg_irs,
        "sell_count": sum(1 for r in results if r["verdict"] == "SELL"),
        "buy_count": sum(1 for r in results if r["verdict"] == "BUY"),
        "mining_metals_exposure": sum(1 for r in results if r.get("is_mining_metals")),
        "sebi_disclaimer": SEBI_DISCLAIMER,
    }


@router.get("/sell-signals")
async def get_sell_signals(
    user: User = Depends(get_current_user),
):
    """Get sell signals from user's watchlist holdings.

    SELL if: G Score < -4 OR Risk Score < -3.5
    NEUTRAL if: G Score < -0.5
    """
    # Fetch user watchlist
    watchlist_data = _supabase_rest(
        "watchlists",
        "GET",
        query={
            "select": "ticker,market",
            "user_id": f"eq.{user.id}",
        },
    )
    if not watchlist_data or not isinstance(watchlist_data, list):
        return {"sell_signals": [], "neutral_signals": [], "sebi_disclaimer": SEBI_DISCLAIMER}

    sell_signals = []
    neutral_signals = []

    for w in watchlist_data:
        ticker = w.get("ticker", "").upper()
        market = w.get("market", "US")

        data = _supabase_rest(
            "anjali_enrichment",
            "GET",
            query={
                "select": "ticker,g_score,risk_score,irs_pct,sector",
                "ticker": f"eq.{ticker}",
                "market": f"eq.{market}",
                "limit": "1",
            },
        )
        if not data or not isinstance(data, list) or len(data) == 0:
            continue

        row = data[0]
        g = row.get("g_score")
        risk = row.get("risk_score")

        if g is not None and g < SELL_G_SCORE_THRESHOLD:
            sell_signals.append({
                "ticker": ticker,
                "market": market,
                "g_score": g,
                "risk_score": risk,
                "irs_pct": row.get("irs_pct"),
                "reason": f"G Score {g} < {SELL_G_SCORE_THRESHOLD}",
                "sector": row.get("sector"),
            })
        elif risk is not None and risk < SELL_RISK_THRESHOLD:
            sell_signals.append({
                "ticker": ticker,
                "market": market,
                "g_score": g,
                "risk_score": risk,
                "irs_pct": row.get("irs_pct"),
                "reason": f"Risk Score {risk} < {SELL_RISK_THRESHOLD}",
                "sector": row.get("sector"),
            })
        elif g is not None and g < NEUTRAL_G_SCORE_THRESHOLD:
            neutral_signals.append({
                "ticker": ticker,
                "market": market,
                "g_score": g,
                "irs_pct": row.get("irs_pct"),
                "note": "May take significant time to show returns",
                "sector": row.get("sector"),
            })

    return {
        "sell_signals": sell_signals,
        "neutral_signals": neutral_signals,
        "sell_count": len(sell_signals),
        "neutral_count": len(neutral_signals),
        "sebi_disclaimer": SEBI_DISCLAIMER,
    }


@router.post("/risk-profile")
async def set_risk_profile(
    risk_profile: Literal["low", "high", "very_high"] = Query(...),
    user: User = Depends(get_current_user),
):
    """Save user's QuantAstra risk profile.

    Low: 100% LM250, near-index returns, ~15-18% expected
    High: 50% LM250 + 30% SmallCap + 20% MicroCap, alpha above index
    Very High: LM250 + SmallCap + MicroCap + Turnaround, highest potential/volatility
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    result = _supabase_rest(
        "user_profiles",
        "PATCH",
        query={"user_id": f"eq.{user.id}"},
        body={
            "astra_risk_profile": risk_profile,
            "risk_profile_set_at": now_iso,
        },
    )

    if result is None:
        # Profile row may not exist — create it
        result = _supabase_rest(
            "user_profiles",
            "POST",
            body={
                "user_id": user.id,
                "astra_risk_profile": risk_profile,
                "risk_profile_set_at": now_iso,
            },
        )

    return {
        "risk_profile": risk_profile,
        "set_at": now_iso,
        "description": {
            "low": "100% Large & MidCap 250. Near-index returns, low volatility.",
            "high": "50% LM250 + 30% SmallCap + 20% MicroCap. Alpha above index.",
            "very_high": "LM250 + SmallCap + MicroCap + Turnaround. Highest potential, highest volatility.",
        }[risk_profile],
    }


@router.get("/geopolitical-scan")
async def geopolitical_scan(
    user: User = Depends(get_current_user),
):
    """Portfolio-level geopolitical risk scan.

    Checks user watchlist for sector exposure to geopolitical risks
    based on current news and high-beta sectors.
    """
    # Fetch user watchlist
    watchlist_data = _supabase_rest(
        "watchlists",
        "GET",
        query={
            "select": "ticker,market",
            "user_id": f"eq.{user.id}",
        },
    )
    if not watchlist_data or not isinstance(watchlist_data, list):
        return {"warnings": [], "total_scanned": 0, "sebi_disclaimer": SEBI_DISCLAIMER}

    # Geopolitically sensitive sectors
    geo_sensitive = {
        "oil & gas", "energy", "defence", "defence & aerospace",
        "pharmaceuticals", "steel", "metals & mining",
        "mining", "commodities",
    }

    warnings = []
    for w in watchlist_data:
        ticker = w.get("ticker", "").upper()
        market = w.get("market", "US")

        data = _supabase_rest(
            "anjali_enrichment",
            "GET",
            query={
                "select": "ticker,sector,qtr_beta,yr_beta,irs_pct",
                "ticker": f"eq.{ticker}",
                "market": f"eq.{market}",
                "limit": "1",
            },
        )
        if not data or not isinstance(data, list) or len(data) == 0:
            continue

        row = data[0]
        sector = (row.get("sector") or "").lower()

        if sector in geo_sensitive:
            beta = row.get("yr_beta") or row.get("qtr_beta")
            risk_level = "HIGH" if beta and beta > 1.5 else "MEDIUM"
            warnings.append({
                "ticker": ticker,
                "sector": row.get("sector"),
                "risk_level": risk_level,
                "beta": beta,
                "irs_pct": row.get("irs_pct"),
                "recommendation": "MONITOR" if risk_level == "MEDIUM" else "REDUCE POSITION",
            })

    return {
        "warnings": warnings,
        "total_scanned": len(watchlist_data),
        "warning_count": len(warnings),
        "sebi_disclaimer": SEBI_DISCLAIMER,
    }