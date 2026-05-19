"""Fit India-specific HMM regime detection model.

Fetches 5 years of daily India macro data from yfinance, trains a 4-state
Gaussian HMM, and saves it alongside the US model.

Features (India analogues to US HMM features):
  india_vix         → VIX (volatility)
  india_vix_20d_chg → VIX 20d change (volatility trend)
  nifty_vs_200ma    → SPX vs 200MA (trend strength)
  inr_usd_1m_chg    → HY spread proxy (currency stress ≈ credit stress in EM)
  nifty_1m_return   → ISM PMI proxy (growth momentum)

Usage: python scripts/fit_hmm_india.py
Output: packages/signals/src/nq_signals/regime/hmm_regime_india.pkl
"""
from __future__ import annotations
import argparse
import pickle
import sys
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

# Ensure packages/signals/src on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))


def fetch_india_macro_history(years: int = 5) -> pd.DataFrame:
    """Download India macro data from yfinance. Returns daily DataFrame."""
    import yfinance as yf

    end = pd.Timestamp.today()
    start = end - pd.DateOffset(years=years)

    print(f"Fetching India macro data {start.date()} → {end.date()}...")

    # India VIX
    print("  ^INDIAVIX...")
    india_vix = yf.download("^INDIAVIX", start=start, end=end, progress=False, auto_adjust=True)
    # Nifty 50
    print("  ^NSEI...")
    nifty = yf.download("^NSEI", start=start, end=end, progress=False, auto_adjust=True)
    # USD/INR
    print("  USDINR=X...")
    usd_inr = yf.download("USDINR=X", start=start, end=end, progress=False, auto_adjust=True)

    df = pd.DataFrame(index=india_vix.index)
    df["india_vix"] = india_vix["Close"]

    # Nifty vs 200MA
    nifty_close = nifty["Close"]
    nifty_200ma = nifty_close.rolling(200).mean()
    df["nifty_vs_200ma"] = (nifty_close - nifty_200ma) / nifty_200ma

    # INR/USD 1-month change (positive = INR weakening = stress)
    inr_close = usd_inr["Close"]
    df["inr_usd_1m_chg"] = inr_close.pct_change(21)  # ~1 month trading days

    # Nifty 1-month return
    df["nifty_1m_return"] = nifty_close.pct_change(21)

    # India VIX 20-day change
    df["india_vix_20d_chg"] = df["india_vix"].diff(20)

    df = df.dropna()
    print(f"  {len(df)} valid rows after dropping NaN")
    return df


def train_and_save(output_path: str, years: int = 5, random_state: int = 42):
    from sklearn.preprocessing import StandardScaler
    from hmmlearn.hmm import GaussianHMM

    df = fetch_india_macro_history(years=years)

    FEATURE_COLS = [
        "india_vix", "india_vix_20d_chg", "nifty_vs_200ma",
        "inr_usd_1m_chg", "nifty_1m_return",
    ]

    X = df[FEATURE_COLS].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print(f"Training India HMM on {len(X_scaled)} rows × {len(FEATURE_COLS)} features...")
    hmm = GaussianHMM(
        n_components=4,
        covariance_type="full",
        n_iter=200,
        random_state=random_state,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hmm.fit(X_scaled)

    if not hmm.monitor_.converged:
        print(f"WARNING: India HMM did not converge after {hmm.n_iter} iterations")
    else:
        print(f"India HMM converged in {hmm.monitor_.iter} iterations")

    # Map HMM states to semantic regimes (same logic as US HMM)
    means = hmm.means_
    stress_scores = means[:, 0] - means[:, 2]  # india_vix - nifty_vs_200ma
    ranking = np.argsort(stress_scores)

    regime_map = {}
    regime_map[int(ranking[0])] = 1  # Least stressed → Risk-On
    regime_map[int(ranking[3])] = 3  # Most stressed → Bear
    mid = [int(ranking[1]), int(ranking[2])]
    pmi_vals = [means[s, 4] for s in mid]  # nifty_1m_return
    if pmi_vals[0] >= pmi_vals[1]:
        regime_map[mid[0]] = 4  # Recovery
        regime_map[mid[1]] = 2  # Late-Cycle
    else:
        regime_map[mid[0]] = 2
        regime_map[mid[1]] = 4

    labels = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}
    print("Regime mapping:")
    for hmm_state, sem_id in sorted(regime_map.items()):
        print(f"  HMM state {hmm_state} → {labels[sem_id]} (id={sem_id})")

    # Store in a dict that mimics RegimeDetector interface
    model = {
        "hmm": hmm,
        "scaler": scaler,
        "regime_map": regime_map,
        "feature_cols": FEATURE_COLS,
        "fitted": True,
        "market": "IN",
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(model, f)
    print(f"India HMM saved to {out} ({out.stat().st_size:,} bytes)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=None, help="Output .pkl path")
    ap.add_argument("--years", type=int, default=5, help="Years of history")
    args = ap.parse_args()

    output = args.output or str(
        ROOT / "packages" / "signals" / "src" / "nq_signals" / "regime" / "hmm_regime_india.pkl"
    )
    train_and_save(output, years=args.years)
    return 0


if __name__ == "__main__":
    sys.exit(main())
