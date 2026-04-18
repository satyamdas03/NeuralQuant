"""Refresh universe JSON files from Wikipedia (S&P 500) + NSE (Nifty 200).

Run: python scripts/refresh_universe.py
Output:
  data/universe/us_sp500.json
  data/universe/in_nifty200.json

Each file is a list of {"ticker","name","sector","subindustry","market_cap_bucket"} dicts.
"""
from __future__ import annotations
import io
import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "universe"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_sp500() -> list[dict]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0 (NeuralQuant universe refresher)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text), attrs={"id": "constituents"})
    df = tables[0].copy()
    df.columns = [c.strip() for c in df.columns]
    # columns: Symbol, Security, GICS Sector, GICS Sub-Industry, ...
    df = df.rename(
        columns={
            "Symbol": "ticker",
            "Security": "name",
            "GICS Sector": "sector",
            "GICS Sub-Industry": "subindustry",
        }
    )
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    rows = df[["ticker", "name", "sector", "subindustry"]].to_dict(orient="records")
    for r in rows:
        r["market_cap_bucket"] = "unknown"
    return rows


def fetch_nifty200() -> list[dict]:
    url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
    headers = {"User-Agent": "Mozilla/5.0 (NeuralQuant universe refresher)"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    # cols: Company Name, Industry, Symbol, Series, ISIN Code
    df = df.rename(
        columns={
            "Symbol": "ticker",
            "Company Name": "name",
            "Industry": "sector",
        }
    )
    df["subindustry"] = df["sector"]
    rows = df[["ticker", "name", "sector", "subindustry"]].to_dict(orient="records")
    for r in rows:
        r["market_cap_bucket"] = "unknown"
    return rows


def main() -> int:
    print("fetching S&P 500…")
    us = fetch_sp500()
    print(f"  got {len(us)} rows")
    (OUT_DIR / "us_sp500.json").write_text(json.dumps(us, indent=2), encoding="utf-8")

    print("fetching Nifty 200…")
    try:
        ind = fetch_nifty200()
        print(f"  got {len(ind)} rows")
        (OUT_DIR / "in_nifty200.json").write_text(json.dumps(ind, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"  WARN nifty fetch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
