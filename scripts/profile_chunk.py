"""Profile single chunk of nightly_score to find bottleneck."""
from __future__ import annotations
import os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))

from nq_api.universe import US_DEFAULT
from nq_api.data_builder import build_real_snapshot
from nq_api.deps import get_signal_engine
from nq_api.sector_rank import apply_sector_adjustment
from nq_api.cache import score_cache
import pandas as pd
import math

CHUNK = 20
tickers = US_DEFAULT[:CHUNK]
print(f"Profiling CHUNK of {len(tickers)} tickers: {tickers[:3]}...{tickers[-3:]}")
print(f"GITHUB_ACTIONS={os.environ.get('GITHUB_ACTIONS', 'not set')}")
print(f"FMP_API_KEY={'set' if os.environ.get('FMP_API_KEY') else 'MISSING'}")

t0_total = time.monotonic()

# Step 1: build_real_snapshot
t0 = time.monotonic()
snapshot = build_real_snapshot(tickers, "US")
t1 = time.monotonic()
print(f"\n[1] build_real_snapshot: {t1 - t0:.1f}s")
if snapshot is not None:
    print(f"    fundamentals: {len(snapshot.fundamentals)} rows, {len(snapshot.fundamentals.columns)} cols")
    print(f"    prices: {len(snapshot.prices)} rows")

# Step 2: SignalEngine.compute
t0 = time.monotonic()
engine = get_signal_engine()
result_df = engine.compute(snapshot)
t1 = time.monotonic()
print(f"[2] engine.compute: {t1 - t0:.1f}s")
if result_df is not None:
    print(f"    result: {len(result_df)} rows")

# Step 3: sector adjustment
t0 = time.monotonic()
result_df = apply_sector_adjustment(result_df, "US")
t1 = time.monotonic()
print(f"[3] sector_adjustment: {t1 - t0:.3f}s")

# Step 4: upsert to Supabase
t0 = time.monotonic()
rows = []
for _, row in result_df.iterrows():
    rows.append({
        "ticker": str(row.get("ticker", "")),
        "market": "US",
        "sector": str(row.get("sector", "")),
        "composite_score": float(row.get("composite_score", 0) if pd.notna(row.get("composite_score")) else 0),
        "rank_score": int(row.get("rank_score", 0) if pd.notna(row.get("rank_score")) else 0),
        "value_percentile": float(row.get("value_percentile", 0.5) if pd.notna(row.get("value_percentile")) else 0.5),
        "momentum_percentile": float(row.get("momentum_percentile", 0.5) if pd.notna(row.get("momentum_percentile")) else 0.5),
        "quality_percentile": float(row.get("quality_percentile", 0.5) if pd.notna(row.get("quality_percentile")) else 0.5),
        "low_vol_percentile": float(row.get("low_vol_percentile", 0.5) if pd.notna(row.get("low_vol_percentile")) else 0.5),
        "short_interest_percentile": float(row.get("short_interest_percentile", 0.5) if pd.notna(row.get("short_interest_percentile")) else 0.5),
        "pe_ttm": float(row.get("pe_ttm", 0)) if pd.notna(row.get("pe_ttm")) else 0,
        "market_cap": float(row.get("market_cap", 0)) if pd.notna(row.get("market_cap")) else 0,
        "current_price": float(row.get("current_price", 0)) if pd.notna(row.get("current_price")) else 0,
        "analyst_target": float(row.get("analyst_target", 0)) if pd.notna(row.get("analyst_target")) else 0,
        "momentum_raw": float(row.get("momentum_raw", 0)) if pd.notna(row.get("momentum_raw")) else 0,
        "gross_profit_margin": float(row.get("gross_profit_margin", 0)) if pd.notna(row.get("gross_profit_margin")) else 0,
        "piotroski": float(row.get("piotroski", 0)) if pd.notna(row.get("piotroski")) else 0,
        "pb_ratio": float(row.get("pb_ratio", 0)) if pd.notna(row.get("pb_ratio")) else 0,
        "beta": float(row.get("beta", 0)) if pd.notna(row.get("beta")) else 0,
        "realized_vol_1y": float(row.get("realized_vol_1y", 0)) if pd.notna(row.get("realized_vol_1y")) else 0,
        "short_interest_pct": float(row.get("short_interest_pct", 0)) if pd.notna(row.get("short_interest_pct")) else 0,
        "insider_cluster_score": float(row.get("insider_cluster_score", 0)) if pd.notna(row.get("insider_cluster_score")) else 0,
        "accruals_ratio": float(row.get("accruals_ratio", 0)) if pd.notna(row.get("accruals_ratio")) else 0,
        "revenue_growth_yoy": float(row.get("revenue_growth_yoy", 0)) if pd.notna(row.get("revenue_growth_yoy")) else 0,
        "debt_equity": float(row.get("debt_equity", 0)) if pd.notna(row.get("debt_equity")) else 0,
    })
count = score_cache.upsert_scores(rows)
t1 = time.monotonic()
print(f"[4] upsert_scores ({count} rows): {t1 - t0:.1f}s")

t1_total = time.monotonic()
print(f"\n=== TOTAL: {t1_total - t0_total:.1f}s ===")
