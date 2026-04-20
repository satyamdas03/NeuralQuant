"""End-to-end health check — hits every public endpoint on prod and reports.

Usage: python scripts/health_check.py [--base https://neuralquant.onrender.com]
Exit 0 iff all public checks pass.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from typing import Any

import requests

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"


def _hit(
    base: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
    expect: tuple[int, ...] = (200,),
) -> tuple[bool, int, Any, float]:
    url = f"{base.rstrip('/')}{path}"
    t0 = time.time()
    try:
        r = requests.request(
            method, url, json=body, headers=headers or {}, timeout=timeout
        )
        elapsed = time.time() - t0
        try:
            payload: Any = r.json()
        except Exception:
            payload = r.text[:200]
        return r.status_code in expect, r.status_code, payload, elapsed
    except Exception as exc:
        return False, 0, str(exc), time.time() - t0


def _fmt(ok: bool, code: int, elapsed: float, note: str = "") -> str:
    tag = PASS if ok else FAIL
    return f"  {tag}  [{code:>3}] {elapsed*1000:6.0f}ms  {note}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://neuralquant.onrender.com")
    args = ap.parse_args()
    base = args.base
    print(f"\nNeuralQuant health check — {base}\n")

    fail_count = 0
    total = 0

    def check(name: str, ok: bool, code: int, elapsed: float, note: str = "") -> None:
        nonlocal fail_count, total
        total += 1
        if not ok:
            fail_count += 1
        print(f"{name}")
        print(_fmt(ok, code, elapsed, note))

    # --- public ---
    ok, code, body, el = _hit(base, "GET", "/health")
    check("/health", ok, code, el, str(body)[:80])

    ok, code, body, el = _hit(base, "GET", "/market/overview")
    n = len(body.get("indices", [])) if isinstance(body, dict) else 0
    check("/market/overview", ok, code, el, f"{n} indices")

    ok, code, body, el = _hit(base, "GET", "/market/news?n=3")
    n = len(body.get("news", [])) if isinstance(body, dict) else 0
    check("/market/news", ok, code, el, f"{n} headlines")

    ok, code, body, el = _hit(base, "GET", "/market/sectors")
    n = len(body.get("sectors", [])) if isinstance(body, dict) else 0
    check("/market/sectors", ok, code, el, f"{n} sectors")

    ok, code, body, el = _hit(base, "GET", "/market/movers")
    g = len(body.get("gainers", [])) if isinstance(body, dict) else 0
    check("/market/movers", ok, code, el, f"{g} gainers")

    ok, code, body, el = _hit(base, "GET", "/screener/preview?market=US&n=5")
    n = len(body.get("results", [])) if isinstance(body, dict) else 0
    regime = body.get("regime_label", "?") if isinstance(body, dict) else "?"
    check("/screener/preview US", ok and n > 0, code, el, f"{n} results · regime={regime}")

    ok, code, body, el = _hit(base, "GET", "/screener/preview?market=IN&n=5")
    n = len(body.get("results", [])) if isinstance(body, dict) else 0
    check("/screener/preview IN", ok and n > 0, code, el, f"{n} results")

    ok, code, body, el = _hit(base, "GET", "/stocks/AAPL?market=US")
    score = body.get("score_1_10", "?") if isinstance(body, dict) else "?"
    check("/stocks/AAPL", ok, code, el, f"score={score}")

    ok, code, body, el = _hit(base, "GET", "/stocks/AAPL/chart?period=1mo&market=US")
    bars = len(body.get("data", [])) if isinstance(body, dict) else 0
    check("/stocks/AAPL/chart", ok, code, el, f"{bars} bars")

    ok, code, body, el = _hit(base, "GET", "/stocks/AAPL/meta?market=US")
    name = body.get("name", "?") if isinstance(body, dict) else "?"
    check("/stocks/AAPL/meta", ok, code, el, f"name={name}")

    ok, code, body, el = _hit(base, "GET", "/sentiment/AAPL?market=US&limit=5", timeout=60)
    n = body.get("n_headlines", 0) if isinstance(body, dict) else 0
    lbl = body.get("label", "?") if isinstance(body, dict) else "?"
    check("/sentiment/AAPL", ok, code, el, f"{n} headlines · {lbl}")

    # --- auth gates (should 401, not 500) ---
    for path, method, body_in in [
        ("/auth/me", "GET", None),
        ("/watchlist", "GET", None),
        ("/query", "POST", {"question": "hi"}),
        ("/screener", "POST", {"market": "US", "max_results": 3}),
        ("/backtest", "POST", {"ticker": "AAPL", "fast": 20, "slow": 50}),
    ]:
        ok, code, body, el = _hit(base, method, path, body=body_in, expect=(401,))
        check(f"auth gate {method} {path}", ok, code, el, "should reject without token")

    # --- summary ---
    print(f"\n{'='*60}")
    if fail_count == 0:
        print(f"{PASS}  {total}/{total} checks passed")
        return 0
    print(f"{FAIL}  {fail_count}/{total} checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
