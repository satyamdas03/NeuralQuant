"""Pre-demo warm-up — hit the live stack so the first audience click is fast.

Run ~3-5 minutes before a demo. It warms the Render service, the data caches,
the Anthropic client, and runs one Ask Morgan query + one PARA-DEBATE so those
heavy paths are hot (their first-hit latency is otherwise ~50s / ~85s — inherent
multi-agent LLM time, not a bug).

Usage:
  python scripts/warmup.py
  python scripts/warmup.py --api https://neuralquant.onrender.com --tickers AAPL,MSFT,NVDA
  python scripts/warmup.py --no-debate          # skip the slow PARA-DEBATE warm

Tip: warm the EXACT tickers you'll demo, so their score/meta/chart are cached.
"""
from __future__ import annotations

import argparse
import sys
import time

import requests


def _get(base: str, path: str, timeout: int = 30) -> tuple[bool, int, float]:
    t0 = time.time()
    try:
        r = requests.get(f"{base.rstrip('/')}{path}", timeout=timeout)
        return r.status_code == 200, r.status_code, time.time() - t0
    except Exception:
        return False, 0, time.time() - t0


def _post(base: str, path: str, body: dict, timeout: int) -> tuple[bool, int, float]:
    t0 = time.time()
    try:
        r = requests.post(f"{base.rstrip('/')}{path}", json=body, timeout=timeout)
        return r.status_code == 200, r.status_code, time.time() - t0
    except Exception:
        return False, 0, time.time() - t0


def _line(name: str, ok: bool, code: int, el: float) -> None:
    tag = "ok " if ok else "FAIL"
    print(f"  [{tag}] {code:>3}  {el*1000:7.0f}ms  {name}")


def main() -> int:
    ap = argparse.ArgumentParser(description="NeuralQuant pre-demo warm-up")
    ap.add_argument("--api", default="https://neuralquant.onrender.com")
    ap.add_argument("--tickers", default="AAPL,MSFT,NVDA,TCS,RELIANCE")
    ap.add_argument("--no-debate", action="store_true", help="skip the ~85s PARA-DEBATE warm")
    args = ap.parse_args()

    base = args.api
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    print(f"\nWarming {base}\n")

    # 1. Service + market data (cheap, warms Render + data caches)
    for path in ["/health", "/market/overview", "/market/sectors", "/market/news?n=3",
                 "/market-wrap/today", "/screener/preview?market=US&n=8",
                 "/screener/preview?market=IN&n=8"]:
        ok, code, el = _get(base, path)
        _line(f"GET {path}", ok, code, el)

    # 2. Per-ticker score/meta/chart (warms the exact demo names)
    for t in tickers:
        market = "IN" if t in {"TCS", "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK"} else "US"
        for path in [f"/stocks/{t}/meta?market={market}",
                     f"/stocks/{t}/chart?period=1mo&market={market}",
                     f"/stocks/{t}?market={market}"]:
            ok, code, el = _get(base, path, timeout=40)
            _line(f"GET {path}", ok, code, el)

    # 3. Ask Morgan (warms Anthropic client + platform cache; first hit ~50s)
    print("\n  warming Ask Morgan (first hit is slow)...")
    ok, code, el = _post(base, "/query/v2",
                         {"question": f"Is {tickers[0]} a buy right now?"}, timeout=90)
    _line("POST /query/v2", ok, code, el)

    # 4. PARA-DEBATE (warms the multi-agent path; first hit ~85s)
    if not args.no_debate:
        print("  warming PARA-DEBATE (first hit ~85s)...")
        ok, code, el = _post(base, "/analyst/stream",
                            {"ticker": tickers[0], "market": "US"}, timeout=180)
        _line("POST /analyst/stream", ok, code, el)

    print("\nWarm. Demo within ~10 min while the service stays hot.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
