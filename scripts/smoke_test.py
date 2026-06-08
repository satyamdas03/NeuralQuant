"""Comprehensive smoke test — hits all major NeuralQuant endpoints including
deep health, authed routes (via SMOKE_TEST_SECRET), and SSE streams.

Usage:
  python scripts/smoke_test.py --api https://neuralquant.onrender.com --cron-secret XXX --smoke-secret YYY

Exit 0 iff all checks pass. JSON report written to smoke_report.json.
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


def _hit_sse(
    base: str,
    path: str,
    *,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> tuple[bool, int, Any, float]:
    """Hit SSE endpoint and parse stream until 'done' or timeout."""
    import httpx

    url = f"{base.rstrip('/')}{path}"
    t0 = time.time()
    try:
        with httpx.stream(
            "POST", url, json=body, headers=headers or {}, timeout=timeout
        ) as resp:
            if resp.status_code != 200:
                try:
                    payload = resp.text[:200]
                except Exception:
                    payload = f"HTTP {resp.status_code}"
                return False, resp.status_code, payload, time.time() - t0

            buffer = ""
            result = None
            for chunk in resp.iter_text():
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines.pop()  # keep incomplete last line
                for line in lines:
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        return False, 200, "Stream closed without result", time.time() - t0
                    try:
                        evt = json.loads(payload)
                        if evt.get("status") == "done":
                            result = evt.get("result")
                            return True, 200, result, time.time() - t0
                        if evt.get("status") == "error":
                            return False, 200, evt.get("message", "SSE error"), time.time() - t0
                    except json.JSONDecodeError:
                        continue

            return False, 200, "SSE stream ended without result", time.time() - t0
    except Exception as exc:
        return False, 0, str(exc), time.time() - t0


def _fmt(ok: bool, code: int, elapsed: float, note: str = "") -> str:
    tag = PASS if ok else FAIL
    return f"  {tag}  [{code:>3}] {elapsed*1000:6.0f}ms  {note}"


def main() -> int:
    ap = argparse.ArgumentParser(description="NeuralQuant comprehensive smoke test")
    ap.add_argument("--api", default="https://neuralquant.onrender.com")
    ap.add_argument("--cron-secret", default="", help="CRON_SECRET for /health/smoke")
    ap.add_argument("--smoke-secret", default="", help="SMOKE_TEST_SECRET for authed endpoints")
    ap.add_argument("--skip-sse", action="store_true", help="Skip SSE-based tests (PARA-DEBATE)")
    ap.add_argument("--json", action="store_true", help="Write JSON report to smoke_report.json")
    args = ap.parse_args()

    base = args.api
    print(f"\nNeuralQuant smoke test — {base}\n")

    results: list[dict] = []
    fail_count = 0
    total = 0

    def record(name: str, ok: bool, code: int, elapsed: float, note: str = ""):
        nonlocal fail_count, total
        total += 1
        if not ok:
            fail_count += 1
        tag = PASS if ok else FAIL
        print(f"  {tag}  [{code:>3}] {elapsed*1000:6.0f}ms  {name:40s} {note}")
        results.append({
            "name": name, "ok": ok, "status": code,
            "latency_ms": int(elapsed * 1000), "note": note,
        })

    # ── 1. Liveness ─────────────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/health")
    record("GET /health", ok, code, el, str(body)[:60])

    # ── 2. Score cache freshness ────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/health/score-cache")
    age = body.get("age_seconds", "?") if isinstance(body, dict) else "?"
    record("GET /health/score-cache", ok, code, el, f"age={age}s")

    # ── 3. Deep smoke (requires CRON_SECRET) ────────────────────────────
    if args.cron_secret:
        hdrs = {"X-Cron-Secret": args.cron_secret}
        ok, code, body, el = _hit(base, "GET", "/health/smoke", headers=hdrs, timeout=20)
        if isinstance(body, dict):
            status = body.get("status", "?")
            summary = body.get("summary", "?")
            record("GET /health/smoke", ok, code, el, f"{status} · {summary}")
        else:
            record("GET /health/smoke", ok, code, el, str(body)[:80])
    else:
        print(f"  {WARN}  GET /health/smoke  SKIPPED (no --cron-secret)")

    # ── 4. Market overview ───────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/market/overview", timeout=15)
    n = len(body.get("indices", [])) if isinstance(body, dict) else 0
    record("GET /market/overview", ok and n > 0, code, el, f"{n} indices")

    # ── 5. Stock meta AAPL ──────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/stocks/AAPL/meta?market=US", timeout=15)
    price = body.get("current_price", "?") if isinstance(body, dict) else "?"
    record("GET /stocks/AAPL/meta", ok, code, el, f"price={price}")

    # ── 6. Stock meta TCS ───────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/stocks/TCS/meta?market=IN", timeout=15)
    price = body.get("current_price", "?") if isinstance(body, dict) else "?"
    record("GET /stocks/TCS/meta", ok, code, el, f"price={price}")

    # ── 7. Stock chart AAPL ─────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/stocks/AAPL/chart?period=1mo&market=US", timeout=15)
    bars = len(body.get("data", [])) if isinstance(body, dict) else 0
    record("GET /stocks/AAPL/chart", ok and bars > 0, code, el, f"{bars} bars")

    # ── 8. Stock score AAPL ──────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/stocks/AAPL?market=US", timeout=30)
    score = body.get("score_1_10", "?") if isinstance(body, dict) else "?"
    record("GET /stocks/AAPL", ok, code, el, f"score={score}")

    # ── 9. Screener preview US ──────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/screener/preview?market=US&n=8")
    n = len(body.get("results", [])) if isinstance(body, dict) else 0
    record("GET /screener/preview US", ok and n > 0, code, el, f"{n} results")

    # ── 10. Market wrap ──────────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/market-wrap/today", timeout=20)
    has_indices = bool(body.get("indices")) if isinstance(body, dict) else False
    record("GET /market-wrap/today", ok, code, el, f"indices={'yes' if has_indices else 'no'}")

    # ── 11. Market news ──────────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/market/news?n=3")
    n = len(body.get("news", [])) if isinstance(body, dict) else 0
    record("GET /market/news", ok and n > 0, code, el, f"{n} headlines")

    # ── 12. Market sectors ──────────────────────────────────────────────
    ok, code, body, el = _hit(base, "GET", "/market/sectors")
    n = len(body.get("sectors", [])) if isinstance(body, dict) else 0
    record("GET /market/sectors", ok and n > 0, code, el, f"{n} sectors")

    # ── 13. Ask Morgan (authed — uses SMOKE_TEST_SECRET) ────────────────
    smoke_hdrs = {"X-Smoke-Secret": args.smoke_secret} if args.smoke_secret else {}
    ok, code, body, el = _hit(
        base, "POST", "/query/v2",
        body={"question": "What is AAPL's current price?"},
        headers=smoke_hdrs or None,
        timeout=30,
    )
    answer = str(body.get("answer", ""))[:60] if isinstance(body, dict) else str(body)[:60]
    record("POST /query/v2", ok, code, el, answer)

    # ── 14. PARA-DEBATE (SSE, authed) ───────────────────────────────────
    if not args.skip_sse:
        ok, code, body, el = _hit_sse(
            base, "/analyst/stream",
            body={"ticker": "AAPL", "market": "US"},
            headers=smoke_hdrs or None,
            timeout=180,
        )
        verdict = str(body.get("verdict", ""))[:40] if isinstance(body, dict) else str(body)[:40]
        record("POST /analyst/stream (SSE)", ok, code, el, verdict)
    else:
        print(f"  {WARN}  POST /analyst/stream  SKIPPED (--skip-sse)")

    # ── 15. Authed: /auth/me with smoke secret ───────────────────────────
    if args.smoke_secret:
        ok, code, body, el = _hit(
            base, "GET", "/auth/me",
            headers=smoke_hdrs,
        )
        email = body.get("email", "?") if isinstance(body, dict) else "?"
        record("GET /auth/me", ok, code, el, email)
    else:
        print(f"  {WARN}  GET /auth/me  SKIPPED (no --smoke-secret)")

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    if fail_count == 0:
        print(f"  {PASS}  {total}/{total} checks passed")
    else:
        print(f"  {FAIL}  {fail_count}/{total} checks failed")

    # JSON report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api": base,
        "total": total,
        "passed": total - fail_count,
        "failed": fail_count,
        "results": results,
    }
    if args.json:
        with open("smoke_report.json", "w") as f:
            json.dump(report, f, indent=2)
        print(f"  Report: smoke_report.json")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())