"""Read-only probe of the public /stocks/{ticker}/meta endpoint (task T11, A4).

Takes the first 50 US and first 50 IN tickers from data/universe/, sends one
unauthenticated GET per ticker, sequentially, with a 1 second sleep between
requests, and writes the results to
docs/verify/evidence/universe_probe_<YYYY-MM-DD>.csv (UTC date).

It never sends POST requests, auth headers, or secrets.

Usage:
    python scripts/verify/probe_universe.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://neuralquant.onrender.com"
PER_MARKET = 50
SLEEP_SECONDS = 1.0
TIMEOUT_SECONDS = 60

ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_FILES = {
    "US": ROOT / "data" / "universe" / "us_sp500.json",
    "IN": ROOT / "data" / "universe" / "in_nifty200.json",
}
EVIDENCE_DIR = ROOT / "docs" / "verify" / "evidence"
FIELDS = [
    "ticker",
    "market",
    "http_code",
    "name",
    "current_price",
    "cached_at",
    "stale",
    "quote_status",
]


def load_tickers(market: str) -> list[str]:
    rows = json.loads(UNIVERSE_FILES[market].read_text(encoding="utf-8"))
    return [r["ticker"] for r in rows[:PER_MARKET]]


def probe(ticker: str, market: str) -> dict:
    url = f"{BASE_URL}/stocks/{urllib.parse.quote(ticker)}/meta?market={market}"
    row = {f: "" for f in FIELDS}
    row.update(ticker=ticker, market=market)
    req = urllib.request.Request(
        url, method="GET", headers={"User-Agent": "nq-verify-probe/1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            row["http_code"] = resp.status
            body = resp.read()
    except urllib.error.HTTPError as e:
        row["http_code"] = e.code
        return row
    except Exception as e:  # network error, timeout
        row["http_code"] = "error"
        row["quote_status"] = f"error:{type(e).__name__}"
        return row
    try:
        data = json.loads(body)
    except ValueError:
        row["quote_status"] = "error:non_json"
        return row
    for f in ("name", "current_price", "cached_at", "stale", "quote_status"):
        v = data.get(f)
        row[f] = "" if v is None else v
    return row


def summarize(rows: list[dict]) -> dict:
    def resolved(r: dict) -> bool:
        name = str(r["name"]).strip()
        t = r["ticker"].upper()
        return bool(name) and name.upper() not in {t, f"{t}.NS"}

    return {
        "total": len(rows),
        "resolved_name": sum(resolved(r) for r in rows),
        "stale": sum(r["stale"] is True for r in rows),
        "errors": sum(
            r["http_code"] == "error" or str(r["quote_status"]).startswith("error:")
            for r in rows
        ),
        "http_not_200": sum(r["http_code"] != 200 for r in rows),
    }


def main() -> int:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = EVIDENCE_DIR / f"universe_probe_{date}.csv"
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict] = []
    first = True
    for market in ("US", "IN"):
        for ticker in load_tickers(market):
            if not first:
                time.sleep(SLEEP_SECONDS)
            first = False
            rows.append(probe(ticker, market))
    finished = datetime.now(timezone.utc).isoformat(timespec="seconds")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"probe window (UTC): {started} .. {finished}")
    print(f"wrote {out.relative_to(ROOT)}")
    for market in ("US", "IN", None):
        subset = [r for r in rows if market is None or r["market"] == market]
        label = market or "ALL"
        s = summarize(subset)
        print(
            f"{label}: total {s['total']}, resolved name {s['resolved_name']}, stale {s['stale']}, "
            f"errors {s['errors']}, http not 200 {s['http_not_200']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
