"""Quarterly performance testing — selection strategy validation.

Tracks MicroCap and SmallCap selection tests against actual returns
to prove the Anjali selection logic generates positive alpha.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/testing/quarterly", tags=["testing"])

SEBI_DISCLAIMER = (
    "QuantAlpha is a research tool, not a SEBI-registered investment advisor. "
    "Quarterly test results are for validation purposes only."
)


def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict] | dict | None = None,
) -> list[dict] | dict | None:
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
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as exc:
        logger.warning("Testing REST %s %s failed: %s", method, table, exc)
        return None


def _require_admin(user: User) -> None:
    if user.tier not in ("pro", "api"):
        raise HTTPException(status_code=403, detail="Admin access required")


def _select_stocks(test_type: str, top_n: int = 10) -> list[dict]:
    """Run selection criteria against current anjali_enrichment data."""
    if test_type == "microcap":
        # MicroCap: both DII+ FII positive, all growth positive, Risk > 0, no Mining
        query: dict[str, Any] = {
            "select": "ticker,market,sector,g_score,risk_score,irs_pct,"
                       "growth_score,dii_quarter,fii_quarter,pe_ratio",
            "market": "eq.IN",
            "irs_pct": "not.is.null",
            "growth_score": "gt.0",
            "risk_score": "gt.0",
            "dii_quarter": "gt.0",
            "fii_quarter": "gt.0",
            "irs_pct": "gte.40",
            "order": "irs_pct.desc",
            "limit": str(top_n * 3),
        }
    else:
        # SmallCap: DII or FII positive, all growth positive, FII quarter > 0, Risk > 0
        query = {
            "select": "ticker,market,sector,g_score,risk_score,irs_pct,"
                       "growth_score,dii_quarter,fii_quarter,pe_ratio",
            "market": "eq.IN",
            "irs_pct": "not.is.null",
            "growth_score": "gt.0",
            "risk_score": "gt.0",
            "fii_quarter": "gt.0",
            "irs_pct": "gte.40",
            "order": "irs_pct.desc",
            "limit": str(top_n * 3),
        }

    data = _supabase_rest("anjali_enrichment", "GET", query=query)
    if not data or not isinstance(data, list):
        return []

    # Filter Mining & Metals
    mining_sectors = {"mining", "metals", "mining & metals"}
    filtered = [
        row for row in data
        if (row.get("sector") or "").lower() not in mining_sectors
    ]

    return filtered[:top_n]


@router.post("/run")
async def run_quarterly_test(
    quarter: str = Query(..., description="e.g. 'Q1FY27'"),
    test_types: list[str] = Query(["microcap", "smallcap"]),
    top_n: int = Query(10, le=20),
    user: User = Depends(get_current_user),
):
    """Run quarterly selection test. Admin only."""
    _require_admin(user)

    today = date.today()
    results = {}

    for test_type in test_types:
        if test_type not in ("microcap", "smallcap"):
            continue

        selected = _select_stocks(test_type, top_n)
        tickers = [s["ticker"] for s in selected]

        # Get current prices
        prices = {}
        for s in selected:
            ticker = s["ticker"]
            try:
                import yfinance as yf
                sym = ticker + ".NS" if not ticker.endswith(".NS") else ticker
                info = yf.Ticker(sym).fast_info
                prices[ticker] = info.get("lastPrice") or info.get("previousClose")
            except Exception:
                prices[ticker] = None

        # Build test results
        test_results = []
        for s in selected:
            ticker = s["ticker"]
            entry_price = prices.get(ticker)
            test_results.append({
                "ticker": ticker,
                "market": "IN",
                "entry_price": entry_price,
                "irs_pct": s.get("irs_pct"),
                "g_score": s.get("g_score"),
                "risk_score": s.get("risk_score"),
            })

        # Store run
        run_body = {
            "run_date": today.isoformat(),
            "quarter": quarter,
            "test_type": test_type,
            "selected_tickers": tickers,
            "selection_criteria": {
                "test_type": test_type,
                "top_n": top_n,
                "filters": {
                    "market": "IN",
                    "growth_positive": True,
                    "risk_positive": True,
                    "mining_excluded": True,
                    "dii_fii_positive": test_type == "microcap",
                    "fii_quarter_positive": True,
                },
            },
            "anjali_snapshot": {s["ticker"]: {"irs_pct": s.get("irs_pct"), "g_score": s.get("g_score")} for s in selected},
        }

        run_result = _supabase_rest("quarterly_test_runs", "POST", body=run_body)
        run_id = None
        if run_result and isinstance(run_result, list) and len(run_result) > 0:
            run_id = run_result[0].get("id")
        elif run_result and isinstance(run_result, dict):
            run_id = run_result.get("id")

        # Store individual results
        if run_id:
            for tr in test_results:
                price = tr["entry_price"]
                if price is not None:
                    _supabase_rest("quarterly_test_results", "POST", body={
                        "run_id": run_id,
                        "ticker": tr["ticker"],
                        "market": tr["market"],
                        "entry_price": price,
                        "notes": f"IRS: {tr.get('irs_pct')}%, G: {tr.get('g_score')}",
                    })

        results[test_type] = {
            "run_id": str(run_id) if run_id else None,
            "quarter": quarter,
            "selected": tickers,
            "count": len(tickers),
            "avg_irs_pct": round(sum(s.get("irs_pct", 0) or 0 for s in selected) / max(len(selected), 1), 1),
        }

    return {"quarter": quarter, "run_date": today.isoformat(), "results": results}


@router.post("/evaluate")
async def evaluate_quarterly_test(
    run_id: str = Query(...),
    user: User = Depends(get_current_user),
):
    """Evaluate a quarterly test run — compute returns and alpha."""
    _require_admin(user)

    # Fetch run
    run_data = _supabase_rest(
        "quarterly_test_runs",
        "GET",
        query={"id": f"eq.{run_id}", "limit": "1"},
    )
    if not run_data or not isinstance(run_data, list) or len(run_data) == 0:
        raise HTTPException(status_code=404, detail="Test run not found")

    run = run_data[0]

    # Fetch results
    results_data = _supabase_rest(
        "quarterly_test_results",
        "GET",
        query={"run_id": f"eq.{run_id}"},
    )
    if not results_data or not isinstance(results_data, list):
        return {"run_id": run_id, "evaluated": 0, "message": "No results to evaluate"}

    # Get current prices for each ticker
    evaluated = []
    for r in results_data:
        ticker = r.get("ticker", "")
        entry_price = r.get("entry_price")
        if not entry_price:
            continue

        try:
            import yfinance as yf
            sym = ticker + ".NS" if not ticker.endswith(".NS") else ticker
            info = yf.Ticker(sym).fast_info
            exit_price = info.get("lastPrice") or info.get("previousClose")
        except Exception:
            exit_price = None

        if exit_price:
            return_pct = round((exit_price - float(entry_price)) / float(entry_price) * 100, 2)
            # TODO: fetch Nifty50 benchmark return for same period
            benchmark_return = None
            alpha = round(return_pct - benchmark_return, 2) if benchmark_return is not None else None

            _supabase_rest(
                "quarterly_test_results",
                "PATCH",
                query={"id": f"eq.{r['id']}"},
                body={
                    "exit_price": exit_price,
                    "return_pct": return_pct,
                    "benchmark_return_pct": benchmark_return,
                    "alpha": alpha,
                    "evaluated_at": date.today().isoformat(),
                },
            )

            evaluated.append({
                "ticker": ticker,
                "entry_price": float(entry_price),
                "exit_price": exit_price,
                "return_pct": return_pct,
                "alpha": alpha,
            })

    avg_return = round(sum(e["return_pct"] for e in evaluated) / max(len(evaluated), 1), 2) if evaluated else None
    avg_alpha = round(sum(e["alpha"] for e in evaluated if e["alpha"] is not None) / max(len([e for e in evaluated if e["alpha"] is not None]), 1), 2) if any(e["alpha"] is not None for e in evaluated) else None

    return {
        "run_id": run_id,
        "quarter": run.get("quarter"),
        "test_type": run.get("test_type"),
        "evaluated_count": len(evaluated),
        "avg_return_pct": avg_return,
        "avg_alpha_pct": avg_alpha,
        "beat_benchmark": avg_alpha is not None and avg_alpha > 0,
        "individual": evaluated,
    }


@router.get("/history")
async def get_test_history(
    user: User = Depends(get_current_user),
):
    """Get all quarterly test runs with summary."""
    _require_admin(user)

    runs = _supabase_rest(
        "quarterly_test_runs",
        "GET",
        query={"select": "*", "order": "run_date.desc", "limit": "50"},
    ) or []

    # Get results count for each run
    history = []
    for run in runs:
        results = _supabase_rest(
            "quarterly_test_results",
            "GET",
            query={
                "select": "id,ticker,entry_price,exit_price,return_pct,alpha,evaluated_at",
                "run_id": f"eq.{run['id']}",
            },
        ) or []

        evaluated = [r for r in results if r.get("evaluated_at")]
        history.append({
            "id": str(run.get("id", "")),
            "quarter": run.get("quarter"),
            "test_type": run.get("test_type"),
            "run_date": run.get("run_date"),
            "selected_count": len(run.get("selected_tickers", [])),
            "evaluated_count": len(evaluated),
            "avg_return": round(sum(r.get("return_pct", 0) or 0 for r in evaluated) / max(len(evaluated), 1), 2) if evaluated else None,
            "avg_alpha": round(sum(r.get("alpha", 0) or 0 for r in evaluated) / max(len(evaluated), 1), 2) if evaluated else None,
        })

    return {"history": history}


@router.get("/equity-curve")
async def get_equity_curve(
    quarter: str = "Q1FY27",
    user: User = Depends(get_current_user),
):
    """
    Returns aggregate quarterly test stats for the landing page backtest section.
    Used by the EquityCurveChart component.
    """
    _require_admin(user)

    try:
        # Fetch the test run for this quarter
        run_resp = _supabase_rest(
            "quarterly_test_runs",
            "GET",
            query={
                "select": "id,selected_tickers,run_date,quarter",
                "quarter": f"eq.{quarter}",
                "order": "created_at.desc",
                "limit": "1",
            },
        )

        if not run_resp or not isinstance(run_resp, list) or len(run_resp) == 0:
            return {
                "quarter": quarter,
                "avg_return": 0,
                "avg_benchmark": 0,
                "alpha": 0,
                "hit_rate": 0,
                "individual_results": [],
                "note": f"No test run found for {quarter}",
            }

        run = run_resp[0]

        # Fetch results
        results_resp = _supabase_rest(
            "quarterly_test_results",
            "GET",
            query={
                "select": "ticker,entry_price,exit_price,return_pct,benchmark_return_pct,alpha,evaluated_at",
                "run_id": f"eq.{run['id']}",
            },
        )

        results = results_resp if results_resp and isinstance(results_resp, list) else []

        # Calculate aggregate stats
        returns = [r["return_pct"] for r in results if r.get("return_pct") is not None]
        benchmark_returns = [r["benchmark_return_pct"] for r in results if r.get("benchmark_return_pct") is not None]

        avg_return = sum(returns) / len(returns) if returns else 0
        avg_benchmark = sum(benchmark_returns) / len(benchmark_returns) if benchmark_returns else 0
        alpha = avg_return - avg_benchmark

        # Hit rate: % of selections that beat benchmark
        if returns and benchmark_returns:
            avg_bench = avg_benchmark
            beats = len([r for r in returns if r > avg_bench])
            hit_rate = beats / len(returns) * 100
        else:
            hit_rate = 0

        return {
            "quarter": quarter,
            "run_date": run.get("run_date"),
            "selected_tickers": run.get("selected_tickers", []),
            "avg_return": round(avg_return, 2),
            "avg_benchmark": round(avg_benchmark, 2),
            "alpha": round(alpha, 2),
            "hit_rate": round(hit_rate, 1),
            "total_selections": len(results),
            "individual_results": results,
        }

    except Exception as e:
        logger.error("Equity curve fetch failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))