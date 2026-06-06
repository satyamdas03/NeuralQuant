#!/usr/bin/env python3
"""Quarterly performance test runner — CLI entry point.

Selects stocks based on Anjali IRS scoring criteria, captures entry prices,
stores snapshots in Supabase, and evaluates prior test runs against actual returns.

Usage:
    # Run selection test (captures current prices as entry)
    python scripts/run_quarterly_test.py --quarter Q1FY27 --market IN --type smallcap
    python scripts/run_quarterly_test.py --quarter Q1FY27 --market IN --type microcap
    python scripts/run_quarterly_test.py --quarter Q1FY27 --market IN --type alpha

    # Evaluate a prior run (fetches current prices, computes returns)
    python scripts/run_quarterly_test.py --evaluate --run-id <UUID>

    # Run ALL pools at once
    python scripts/run_quarterly_test.py --quarter Q1FY27 --market IN --all

    # Retroactive backtest: apply criteria NOW, compare 3-month returns vs NIFTY50
    python scripts/run_quarterly_test.py --quarter Q1FY27 --market IN --backtest
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger("quarterly_test")

# ── Selection pools (Phase 3 spec) ───────────────────────────────────────────

POOL_A_CRITERIA = {
    "name": "LM250 Alpha",
    "description": "G Score > 0, Risk Efficiency > 0, IRS% > 65%",
    "filters": {
        "g_score": ("gt", 0),
        "risk_eff_score": ("gt", 0),
        "irs_pct": ("gte", 65),
    },
    "exclude_sectors": ["Mining", "Metals"],
    "max_n": 25,
}

POOL_B_CRITERIA = {
    "name": "SmallCap / MicroCap",
    "description": "G Score > 0, IRS% > 50%, Risk Score > 0",
    "filters": {
        "g_score": ("gt", 0),
        "risk_score": ("gt", 0),
        "irs_pct": ("gte", 50),
    },
    "exclude_sectors": ["Mining", "Metals"],
    "max_n": 20,
}

POOL_C_CRITERIA = {
    "name": "Turnaround",
    "description": "QoQ profit growth > 0, Risk Efficiency > 0, IRS% > 40",
    "filters": {
        "qoq_profit_growth": ("gt", 0),
        "risk_eff_score": ("gt", 0),
        "irs_pct": ("gte", 40),
    },
    "exclude_sectors": ["Mining", "Metals"],
    "max_n": 15,
}

# Map CLI --type to pool
POOL_MAP = {
    "alpha": POOL_A_CRITERIA,
    "smallcap": POOL_B_CRITERIA,
    "microcap": POOL_C_CRITERIA,
}


def _supabase_rest(table, method="GET", query=None, body=None):
    """Direct Supabase PostgREST call."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)
    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    try:
        with httpx.Client(timeout=30) as client:
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
        logger.error("Supabase REST %s %s failed: %s", method, table, exc)
        return None


def _fetch_anjali_data(market: str) -> list[dict]:
    """Fetch all QuantFactor enrichment data for a market."""
    logger.info("Fetching QuantFactor data for market=%s", market)
    all_rows = []
    offset = 0
    limit = 500
    while True:
        data = _supabase_rest("anjali_enrichment", "GET", query={
            "market": f"eq.{market}",
            "select": "*",
            "order": "irs_pct.desc.nullslast",
            "limit": str(limit),
            "offset": str(offset),
        })
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        all_rows.extend(data)
        if len(data) < limit:
            break
        offset += limit
    logger.info("Loaded %d stocks from QuantFactor enrichment", len(all_rows))
    return all_rows


def _get_current_price(ticker: str, market: str = "IN") -> float | None:
    """Get current price via yfinance."""
    try:
        import yfinance as yf
        sym = ticker + ".NS" if market == "IN" and not ticker.endswith(".NS") else ticker
        t = yf.Ticker(sym)
        info = t.fast_info
        price = info.get("lastPrice") or info.get("previousClose")
        if price:
            return round(float(price), 2)
        # Fallback: try history
        hist = t.history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception as e:
        logger.warning("Price fetch failed for %s: %s", ticker, e)
    return None


def _get_nifty50_3m_return() -> float | None:
    """Get NIFTY50 3-month return as benchmark."""
    try:
        import yfinance as yf
        t = yf.Ticker("^NSEI")
        hist = t.history(period="3mo")
        if len(hist) >= 2:
            start = hist["Close"].iloc[0]
            end = hist["Close"].iloc[-1]
            return round((end - start) / start * 100, 2)
    except Exception as e:
        logger.warning("NIFTY50 benchmark fetch failed: %s", e)
    return None


def select_stocks(stocks: list[dict], criteria: dict) -> list[dict]:
    """Filter stocks by criteria and return top-N sorted by IRS%."""
    filtered = stocks.copy()

    for col, (op, val) in criteria["filters"].items():
        if col not in filtered[0] if filtered else []:
            logger.warning("Column %s not in data, skipping filter", col)
            continue
        if op == "gt":
            filtered = [s for s in filtered if s.get(col) is not None and s[col] > val]
        elif op == "gte":
            filtered = [s for s in filtered if s.get(col) is not None and s[col] >= val]
        elif op == "lt":
            filtered = [s for s in filtered if s.get(col) is not None and s[col] < val]
        elif op == "lte":
            filtered = [s for s in filtered if s.get(col) is not None and s[col] <= val]

    # Exclude Mining & Metals
    mining_sectors = {"mining", "metals", "mining & metals"}
    filtered = [
        s for s in filtered
        if (s.get("sector") or "").lower() not in mining_sectors
    ]

    # Sort by IRS% descending
    filtered.sort(key=lambda s: s.get("irs_pct") or 0, reverse=True)

    return filtered[: criteria.get("max_n", 25)]


def run_test(quarter: str, market: str, pool_type: str) -> dict | None:
    """Run quarterly test — select stocks, capture prices, store snapshot."""
    criteria = POOL_MAP.get(pool_type)
    if not criteria:
        logger.error("Unknown pool type: %s", pool_type)
        return None

    stocks = _fetch_anjali_data(market)
    if not stocks:
        logger.error("No stocks found for market=%s", market)
        return None

    selected = select_stocks(stocks, criteria)
    logger.info("Selected %d stocks for %s (%s)", len(selected), pool_type, criteria["name"])

    if not selected:
        logger.warning("No stocks passed filters for %s", pool_type)
        return None

    # Capture entry prices
    logger.info("Capturing entry prices via yfinance...")
    for s in selected:
        price = _get_current_price(s["ticker"], market)
        s["entry_price"] = price
        if price:
            logger.info("  %s: ₹%.2f (IRS %.0f%%, G %.1f)", s["ticker"], price, s.get("irs_pct", 0), s.get("g_score", 0))
        else:
            logger.warning("  %s: price unavailable", s["ticker"])

    # Store test run
    # DB constraint allows only 'microcap' | 'smallcap'; map 'alpha' -> 'smallcap'
    db_test_type = "smallcap" if pool_type == "alpha" else pool_type
    run_body = {
        "run_date": date.today().isoformat(),
        "quarter": quarter,
        "test_type": db_test_type,
        "selected_tickers": [s["ticker"] for s in selected],
        "selection_criteria": {
            "pool_type": pool_type,
            "name": criteria["name"],
            "description": criteria["description"],
            "filters": criteria["filters"],
            "exclude_sectors": criteria["exclude_sectors"],
        },
        "anjali_snapshot": [
            {
                "ticker": s["ticker"],
                "name": s.get("name", ""),
                "sector": s.get("sector", ""),
                "irs_pct": s.get("irs_pct"),
                "g_score": s.get("g_score"),
                "risk_eff_score": s.get("risk_eff_score"),
                "risk_score": s.get("risk_score"),
                "composite": s.get("composite_anjali_score"),
                "pe_ratio": s.get("pe_ratio"),
                "entry_price": s.get("entry_price"),
            }
            for s in selected
        ],
    }

    run_result = _supabase_rest("quarterly_test_runs", "POST", body=run_body)
    if not run_result:
        logger.error("Failed to store test run")
        return None

    run = run_result[0] if isinstance(run_result, list) else run_result
    run_id = run.get("id")

    # Store individual results with entry prices
    stored = 0
    for s in selected:
        if s.get("entry_price"):
            _supabase_rest("quarterly_test_results", "POST", body={
                "run_id": run_id,
                "ticker": s["ticker"],
                "market": market,
                "entry_price": s["entry_price"],
                "notes": f"IRS: {s.get('irs_pct', 0):.0f}%, G: {s.get('g_score', 0):.1f}",
            })
            stored += 1

    logger.info("Stored test run: id=%s, quarter=%s, type=%s", run_id, quarter, pool_type)
    logger.info("Stored %d individual results with entry prices", stored)

    return {
        "run_id": str(run_id),
        "pool": criteria["name"],
        "quarter": quarter,
        "count": len(selected),
        "stored_with_price": stored,
        "avg_irs_pct": round(sum(s.get("irs_pct", 0) or 0 for s in selected) / len(selected), 1),
        "avg_g_score": round(sum(s.get("g_score", 0) or 0 for s in selected) / len(selected), 1),
        "tickers": [s["ticker"] for s in selected],
    }


def evaluate_test(run_id: str) -> dict | None:
    """Evaluate a prior test run — fetch current prices, compute returns."""
    # Fetch run
    runs = _supabase_rest("quarterly_test_runs", "GET", query={
        "id": f"eq.{run_id}", "select": "*", "limit": "1",
    })
    if not runs or not isinstance(runs, list) or len(runs) == 0:
        logger.error("Test run %s not found", run_id)
        return None

    run = runs[0]
    market = "IN"

    # Fetch results
    results = _supabase_rest("quarterly_test_results", "GET", query={
        "run_id": f"eq.{run_id}", "select": "*",
    })
    if not results or not isinstance(results, list):
        logger.error("No results found for run %s", run_id)
        return None

    logger.info("Evaluating run %s: %d tickers, quarter=%s", run_id, len(results), run["quarter"])

    # Get benchmark return
    benchmark_return = _get_nifty50_3m_return()
    logger.info("NIFTY50 3-month return: %s%%", benchmark_return)

    evaluated = []
    for r in results:
        ticker = r.get("ticker", "")
        entry_price = r.get("entry_price")
        if not entry_price:
            continue

        exit_price = _get_current_price(ticker, market)
        if exit_price:
            return_pct = round((exit_price - float(entry_price)) / float(entry_price) * 100, 2)
            alpha = round(return_pct - benchmark_return, 2) if benchmark_return is not None else None

            _supabase_rest("quarterly_test_results", "PATCH", query={
                "id": f"eq.{r['id']}",
            }, body={
                "exit_price": exit_price,
                "return_pct": return_pct,
                "benchmark_return_pct": benchmark_return,
                "alpha": alpha,
                "evaluated_at": date.today().isoformat(),
            })

            evaluated.append({
                "ticker": ticker,
                "entry_price": float(entry_price),
                "exit_price": exit_price,
                "return_pct": return_pct,
                "alpha": alpha,
            })
            logger.info("  %s: entry=₹%.2f exit=₹%.2f return=%.2f%% alpha=%s%%",
                        ticker, float(entry_price), exit_price, return_pct,
                        f"{alpha:.2f}" if alpha is not None else "N/A")

    if not evaluated:
        logger.warning("No stocks could be evaluated")
        return None

    avg_return = round(sum(e["return_pct"] for e in evaluated) / len(evaluated), 2)
    alpha_values = [e["alpha"] for e in evaluated if e["alpha"] is not None]
    avg_alpha = round(sum(alpha_values) / len(alpha_values), 2) if alpha_values else None
    beat_count = sum(1 for e in evaluated if e["alpha"] is not None and e["alpha"] > 0)
    hit_rate = round(beat_count / len(evaluated) * 100, 1) if evaluated else 0

    result = {
        "run_id": run_id,
        "quarter": run.get("quarter"),
        "test_type": run.get("test_type"),
        "evaluated_count": len(evaluated),
        "avg_return_pct": avg_return,
        "benchmark_return_pct": benchmark_return,
        "avg_alpha_pct": avg_alpha,
        "beat_benchmark": avg_alpha is not None and avg_alpha > 0,
        "hit_rate_pct": hit_rate,
        "individual": evaluated,
    }

    logger.info("\n=== EVALUATION SUMMARY ===")
    logger.info("Quarter: %s", run.get("quarter"))
    logger.info("Stocks evaluated: %d", len(evaluated))
    logger.info("Average return: %.2f%%", avg_return)
    logger.info("NIFTY50 benchmark: %s%%", benchmark_return)
    logger.info("Average alpha: %s%%", f"{avg_alpha:.2f}" if avg_alpha is not None else "N/A")
    logger.info("Hit rate (beat benchmark): %.1f%%", hit_rate)
    logger.info("BEAT BENCHMARK: %s", "YES [OK]" if avg_alpha is not None and avg_alpha > 0 else "NO [FAIL]")

    return result


def run_backtest(quarter: str, market: str) -> dict:
    """Retroactive backtest: select stocks NOW, compute 3-month returns using yfinance history."""
    import yfinance as yf

    stocks = _fetch_anjali_data(market)
    if not stocks:
        logger.error("No stocks found")
        return {}

    # Get NIFTY50 3-month return as benchmark
    benchmark_return = _get_nifty50_3m_return()
    logger.info("NIFTY50 3-month return: %s%%", benchmark_return)

    results = {}
    for pool_type, criteria in POOL_MAP.items():
        selected = select_stocks(stocks, criteria)
        if not selected:
            logger.info("No stocks for %s pool", pool_type)
            continue

        logger.info("\n%s (%s): %d stocks", criteria["name"], pool_type, len(selected))

        # Get 3-month returns for each stock
        pool_results = []
        for s in selected:
            ticker = s["ticker"]
            try:
                sym = ticker + ".NS" if not ticker.endswith(".NS") else ticker
                t = yf.Ticker(sym)
                hist = t.history(period="3mo")
                if len(hist) >= 2:
                    start_price = hist["Close"].iloc[0]
                    end_price = hist["Close"].iloc[-1]
                    return_pct = round((end_price - start_price) / start_price * 100, 2)
                    alpha = round(return_pct - benchmark_return, 2) if benchmark_return is not None else None
                    pool_results.append({
                        "ticker": ticker,
                        "name": s.get("name", ""),
                        "irs_pct": s.get("irs_pct"),
                        "g_score": s.get("g_score"),
                        "return_3m_pct": return_pct,
                        "alpha": alpha,
                    })
                    logger.info("  %s: IRS %.0f%% 3m return %.2f%% alpha %s%%",
                                ticker, s.get("irs_pct", 0), return_pct,
                                f"{alpha:.2f}" if alpha is not None else "N/A")
            except Exception as e:
                logger.warning("  %s: yfinance failed: %s", ticker, e)

        if pool_results:
            avg_return = round(sum(p["return_3m_pct"] for p in pool_results) / len(pool_results), 2)
            alpha_vals = [p["alpha"] for p in pool_results if p["alpha"] is not None]
            avg_alpha = round(sum(alpha_vals) / len(alpha_vals), 2) if alpha_vals else None
            beat_count = sum(1 for p in pool_results if p.get("alpha") is not None and p["alpha"] > 0)
            hit_rate = round(beat_count / len(pool_results) * 100, 1)

            results[pool_type] = {
                "pool_name": criteria["name"],
                "count": len(pool_results),
                "avg_return_pct": avg_return,
                "benchmark_return_pct": benchmark_return,
                "avg_alpha_pct": avg_alpha,
                "hit_rate_pct": hit_rate,
                "beat_benchmark": avg_alpha is not None and avg_alpha > 0,
                "stocks": pool_results,
            }

            logger.info("\n--- %s SUMMARY ---", criteria["name"])
            logger.info("Stocks: %d", len(pool_results))
            logger.info("Avg 3m return: %.2f%%", avg_return)
            logger.info("NIFTY50 benchmark: %s%%", benchmark_return)
            logger.info("Avg alpha: %s%%", f"{avg_alpha:.2f}" if avg_alpha is not None else "N/A")
            logger.info("Hit rate: %.1f%%", hit_rate)
            logger.info("BEAT BENCHMARK: %s", "YES [OK]" if avg_alpha is not None and avg_alpha > 0 else "NO [FAIL]")

    return results


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Quarterly Performance Test Runner")
    parser.add_argument("--quarter", default="Q1FY27", help="Quarter label (e.g., Q1FY27)")
    parser.add_argument("--market", default="IN", choices=["US", "IN"], help="Market")
    parser.add_argument("--type", default="smallcap", choices=["microcap", "smallcap", "alpha"], help="Pool type")
    parser.add_argument("--all", action="store_true", help="Run all pools")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate a prior run")
    parser.add_argument("--run-id", help="Run ID to evaluate")
    parser.add_argument("--backtest", action="store_true", help="Retroactive backtest (3m returns)")
    args = parser.parse_args()

    # Load env vars from apps/api/.env if not set
    if not os.environ.get("SUPABASE_URL"):
        env_file = Path(__file__).resolve().parents[1] / "apps" / "api" / ".env"
        if env_file.exists():
            logger.info("Loading env from %s", env_file)
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    if args.evaluate:
        if not args.run_id:
            logger.error("--run-id required for evaluation")
            sys.exit(1)
        result = evaluate_test(args.run_id)
        if result:
            print(json.dumps(result, indent=2))
        return

    if args.backtest:
        results = run_backtest(args.quarter, args.market)
        print(json.dumps(results, indent=2, default=str))
        return

    if args.all:
        pool_types = ["alpha", "smallcap", "microcap"]
    else:
        pool_types = [args.type]

    all_results = []
    for pool_type in pool_types:
        logger.info("\n=== Running %s pool ===", pool_type)
        result = run_test(args.quarter, args.market, pool_type)
        if result:
            all_results.append(result)
            print(f"\n[OK] {result['pool']}: {result['count']} stocks selected (avg IRS {result['avg_irs_pct']}%)")
            print(f"   Tickrs: {', '.join(result['tickers'][:10])}{'...' if len(result['tickers']) > 10 else ''}")
            print(f"   Run ID: {result['run_id']}")
        else:
            print(f"\nX {pool_type}: No stocks selected")

    if all_results:
        print(f"\n=== QUARTERLY TEST COMPLETE: {args.quarter} ===")
        for r in all_results:
            print(f"  {r['pool']}: {r['count']} stocks, avg IRS {r['avg_irs_pct']}%, stored {r['stored_with_price']} with prices")
        print("\nTo evaluate later, run:")
        for r in all_results:
            print(f"  python scripts/run_quarterly_test.py --evaluate --run-id {r['run_id']}")


if __name__ == "__main__":
    main()