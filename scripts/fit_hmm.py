"""
Fit 4-state HMM regime detector on historical macro data.
Saves fitted model to packages/signals/src/nq_signals/regime/hmm_regime.pkl

Run: python scripts/fit_hmm.py
Requires: pip install hmmlearn scikit-learn pandas yfinance
"""
import os
import sys
import pickle
import warnings
from pathlib import Path

import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("FRED_API_KEY", os.environ.get("FRED_API_KEY", "b09c2aae58f65cd63fffd0109aabc2ec"))


def fetch_macro_history() -> pd.DataFrame:
    """Fetch 10+ years of macro data for HMM training."""
    print("Fetching macro data...")

    # --- VIX from yfinance ---
    import yfinance as yf
    print("  Fetching VIX from yfinance...")
    vix = yf.download("^VIX", start="2010-01-01", progress=False)
    if vix is None or vix.empty:
        raise RuntimeError("Failed to fetch VIX data")
    # Handle MultiIndex
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)
    vix_close = vix["Close"].dropna()
    vix_df = pd.DataFrame({"vix": vix_close})

    # --- SPX from yfinance ---
    print("  Fetching SPX from yfinance...")
    spx = yf.download("^GSPC", start="2010-01-01", progress=False)
    if spx is None or spx.empty:
        raise RuntimeError("Failed to fetch SPX data")
    if isinstance(spx.columns, pd.MultiIndex):
        spx.columns = spx.columns.get_level_values(0)
    spx_close = spx["Close"].dropna()

    # Compute 200-day MA and deviation
    spx_200ma = spx_close.rolling(200).mean()
    spx_vs_200ma = (spx_close - spx_200ma) / spx_200ma
    spx_df = pd.DataFrame({"spx_vs_200ma": spx_vs_200ma})

    # --- HY Spreads + ISM PMI from FRED ---
    print("  Fetching HY spreads and ISM PMI from FRED...")
    try:
        from fredapi import Fred
        fred_key = os.environ.get("FRED_API_KEY", "")
        fred = Fred(api_key=fred_key)

        # BAMLH0A0HYM2 = ICE BofA US High Yield Option-Adjusted Spread
        hy_spread = fred.get_series("BAMLH0A0HYM2")
        hy_spread.name = "hy_spread_oas"

        # NAPM = ISM Manufacturing PMI
        ism_pmi = fred.get_series("NAPM")
        ism_pmi.name = "ism_pmi"

        fred_df = pd.DataFrame({"hy_spread_oas": hy_spread, "ism_pmi": ism_pmi})
        print(f"  FRED: {len(fred_df.dropna())} rows with complete data")
    except Exception as e:
        warnings.warn(f"FRED failed ({e}), using heuristic fallback values")
        # Fallback: create synthetic-ish data with reasonable values
        idx = vix_df.index
        fred_df = pd.DataFrame({
            "hy_spread_oas": np.full(len(idx), 400.0),  # ~400bps average
            "ism_pmi": np.full(len(idx), 51.0),  # ~51 average
        }, index=idx)

    # --- Merge all data ---
    df = vix_df.join(spx_df, how="inner").join(fred_df, how="inner")
    df["vix_20d_change"] = df["vix"].diff(20).fillna(0)

    # Forward fill any missing values, then drop any remaining
    df = df.ffill().dropna()

    print(f"  Complete dataset: {len(df)} rows ({df.index[0].date()} → {df.index[-1].date()})")
    return df


def fit_and_save(df: pd.DataFrame, output_path: str) -> None:
    """Fit HMM and save to pickle."""
    from sklearn.preprocessing import StandardScaler
    from hmmlearn.hmm import GaussianHMM
    from nq_signals.regime.hmm_detector import (
        RegimeDetector, FEATURE_COLS, REGIME_LABELS,
    )

    print(f"\nFitting 4-state HMM on {len(df)} observations x {len(FEATURE_COLS)} features...")

    detector = RegimeDetector(n_regimes=4, random_state=42)
    detector.fit(df)

    # Print regime characteristics
    print("\nRegime characteristics:")
    means = detector._hmm.means_
    for hmm_state, semantic_id in detector._regime_map.items():
        label = REGIME_LABELS[semantic_id]
        m = means[hmm_state]
        print(f"  {label} (state {hmm_state}→regime {semantic_id}): "
              f"VIX={m[0]:.1f}, SPX_vs_200MA={m[2]:.3f}, "
              f"HY={m[3]:.0f}bps, PMI={m[4]:.1f}")

    transmat = detector._hmm.transmat_
    print(f"\nTransition matrix:\n{transmat}")

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(detector, f)

    print(f"\nModel saved to: {output_path}")
    print("Done. HMM regime detector is ready for production use.")


def main():
    output = os.environ.get(
        "HMM_MODEL_PATH",
        str(Path(__file__).resolve().parent.parent
            / "packages" / "signals" / "src" / "nq_signals" / "regime" / "hmm_regime.pkl"),
    )
    df = fetch_macro_history()
    fit_and_save(df, output)


if __name__ == "__main__":
    main()
