"""Production end-to-end audit for NeuralQuant.

Tests public/unauthed endpoints against the live Render API.
Does NOT require secrets. Writes a JSON report to prod_audit_report.json.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any

import requests

BASE = "https://neuralquant.onrender.com"
OPENBB = "https://nq-openbb.onrender.com"
TIMEOUT = 30

results: list[dict[str, Any]] = []
failures = 0
warnings = 0


def log(name: str, ok: bool, status: int, latency: float, note: str = "") -> None:
    global failures, warnings
    tag = "PASS" if ok else "FAIL"
    if not ok:
        failures += 1
    print(f"  {tag}  [{status:>3}] {latency * 1000:6.0f}ms  {name:45s} {note}")
    results.append({"name": name, "ok": ok, "status": status, "latency_ms": round(latency * 1000, 1), "note": note})


def hit(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = TIMEOUT) -> tuple[bool, int, Any, float]:
    url = f"{BASE}{path}"
    t0 = time.time()
    try:
        r = requests.request(method, url, json=body, timeout=timeout)
        el = time.time() - t0
        try:
            payload = r.json()
        except Exception:
            payload = r.text[:200]
        return r.status_code < 400, r.status_code, payload, el
    except Exception as exc:
        return False, 0, str(exc), time.time() - t0


def validate_list(payload: Any, key: str) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "not a dict"
    lst = payload.get(key)
    if not isinstance(lst, list):
        return False, f"missing {key}"
    return len(lst) > 0, f"{len(lst)} items"


def main() -> int:
    print(f"\nNeuralQuant production audit — {BASE}\n")

    # 1. Liveness & freshness
    ok, code, body, el = hit("GET", "/health")
    version = body.get("version", "?") if isinstance(body, dict) else "?"
    log("GET /health", ok, code, el, f"version={version}")

    ok, code, body, el = hit("GET", "/health/score-cache")
    age = body.get("age_seconds", "?") if isinstance(body, dict) else "?"
    rows = body.get("rows", "?") if isinstance(body, dict) else "?"
    log("GET /health/score-cache", ok, code, el, f"age={age}s rows={rows}")

    # 2. Market surfaces
    ok, code, body, el = hit("GET", "/market/overview", timeout=15)
    n = len(body.get("indices", [])) if isinstance(body, dict) else 0
    log("GET /market/overview", ok and n > 0, code, el, f"{n} indices")

    ok, code, body, el = hit("GET", "/market/sectors", timeout=15)
    v_ok, note = validate_list(body, "sectors")
    log("GET /market/sectors", ok and v_ok, code, el, note)

    ok, code, body, el = hit("GET", "/market/news?n=3", timeout=15)
    v_ok, note = validate_list(body, "news")
    log("GET /market/news", ok and v_ok, code, el, note)

    ok, code, body, el = hit("GET", "/market/movers?market=US", timeout=15)
    v_ok, note = validate_list(body, "gainers")
    log("GET /market/movers US", ok and v_ok, code, el, note)

    ok, code, body, el = hit("GET", "/market-wrap/today", timeout=20)
    v_ok, note = validate_list(body, "indices")
    log("GET /market-wrap/today", ok and v_ok, code, el, note)

    # 3. Stock endpoints (data accuracy proxies)
    # /stocks/{ticker} returns AIScore (score fields, no current_price)
    ok, code, body, el = hit("GET", "/stocks/AAPL?market=US", timeout=30)
    score = body.get("score_1_10", "?") if isinstance(body, dict) else "?"
    log("GET /stocks/AAPL", ok and score not in (None, "?"), code, el, f"score={score}")

    ok, code, body, el = hit("GET", "/stocks/TCS?market=IN", timeout=30)
    score = body.get("score_1_10", "?") if isinstance(body, dict) else "?"
    log("GET /stocks/TCS", ok and score not in (None, "?"), code, el, f"score={score}")

    # /stocks/{ticker}/meta returns name + current_price
    ok, code, body, el = hit("GET", "/stocks/AAPL/meta?market=US", timeout=15)
    name = body.get("name", "?") if isinstance(body, dict) else "?"
    price = body.get("current_price", "?") if isinstance(body, dict) else "?"
    log("GET /stocks/AAPL/meta", ok and name not in (None, "?"), code, el, f"name={name} price={price}")

    ok, code, body, el = hit("GET", "/stocks/TCS/meta?market=IN", timeout=15)
    name = body.get("name", "?") if isinstance(body, dict) else "?"
    price = body.get("current_price", "?") if isinstance(body, dict) else "?"
    log("GET /stocks/TCS/meta", ok and name not in (None, "?"), code, el, f"name={name} price={price}")

    ok, code, body, el = hit("GET", "/stocks/AAPL/chart?period=1mo&market=US", timeout=15)
    v_ok, note = validate_list(body, "data")
    log("GET /stocks/AAPL/chart", ok and v_ok, code, el, note)

    # 4. Screener
    ok, code, body, el = hit("GET", "/screener/preview?market=US&n=5", timeout=20)
    v_ok, note = validate_list(body, "results")
    log("GET /screener/preview US", ok and v_ok, code, el, note)

    ok, code, body, el = hit("GET", "/screener/preview?market=IN&n=5", timeout=20)
    v_ok, note = validate_list(body, "results")
    log("GET /screener/preview IN", ok and v_ok, code, el, note)

    # 5. Trade signals
    ok, code, body, el = hit("GET", "/trade/signals?market=US&n=5", timeout=20)
    v_ok, note = validate_list(body, "signals")
    log("GET /trade/signals US", ok and v_ok, code, el, note)

    ok, code, body, el = hit("GET", "/trade/signals?market=IN&n=5", timeout=20)
    v_ok, note = validate_list(body, "signals")
    log("GET /trade/signals IN", ok and v_ok, code, el, note)

    # 6. Ask Morgan (structured) — moderate timeout
    ok, code, body, el = hit("POST", "/query/v2", body={"question": "What is AAPL's current price?"}, timeout=60)
    summary = str(body.get("summary", "?"))[:60] if isinstance(body, dict) else str(body)[:60]
    log("POST /query/v2", ok, code, el, summary)

    # 7. Public quarterly results
    ok, code, body, el = hit("GET", "/testing/quarterly/public-results", timeout=15)
    summary = body.get("summary", {}) if isinstance(body, dict) else {}
    pools = body.get("pool_breakdown", []) if isinstance(body, dict) else []
    v_ok = isinstance(summary, dict) and len(pools) > 0
    note = f"summary keys={list(summary.keys()) if isinstance(summary, dict) else '?'} pools={len(pools)}"
    log("GET /testing/quarterly/public-results", ok and v_ok, code, el, note)

    # 8. Hermes proxy (the reported failure)
    for hpath in ["/hermes/status", "/hermes/strategy", "/hermes/trades"]:
        ok, code, body, el = hit("GET", hpath, timeout=15)
        msg = str(body.get("detail", body))[:60] if isinstance(body, dict) else str(body)[:60]
        log(f"GET {hpath}", ok, code, el, msg)

    # 9. OpenBB proxy health
    t0 = time.time()
    try:
        r = requests.get(f"{OPENBB}/docs", timeout=15)
        el = time.time() - t0
        log("GET nq-openbb /docs", r.status_code < 400, r.status_code, el, r.text[:40])
    except Exception as exc:
        el = time.time() - t0
        log("GET nq-openbb /docs", False, 0, el, str(exc))

    # 10. Authed endpoints without auth (should 401, not 500)
    ok, code, body, el = hit("GET", "/auth/me", timeout=10)
    log("GET /auth/me (no auth)", code == 401, code, el, f"expected 401 got {code}")

    ok, code, body, el = hit("GET", "/health/smoke", timeout=10)
    log("GET /health/smoke (no secret)", code == 403, code, el, f"expected 403 got {code}")

    # Summary
    total = len(results)
    passed = total - failures
    print(f"\n{'='*80}")
    print(f"  TOTAL: {total}  |  PASS: {passed}  |  FAIL: {failures}")
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api": BASE,
        "total": total,
        "passed": passed,
        "failed": failures,
        "results": results,
    }
    with open("prod_audit_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("  Report: prod_audit_report.json")
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
