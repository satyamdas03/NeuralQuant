"""
Backtest runner — validates signal engine on historical quarters.
Uses walk-forward validation: train on past, evaluate on out-of-sample future.

Usage:
    uv run python scripts/backtest/run_backtest.py --data-dir data/backtest --output results/backtest

Expects CSV files in data-dir with columns (V8 format):
  ProcessDate, NseCode, Return, ROE_score, 3M_Return_score, PE_Ratio_score,
  Beta_score, HoldingScore, ...

Output:
  results/ic_by_period.csv  — IC per quarter
  results/summary.txt       — human-readable summary
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow importing from packages/ without installing
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "packages" / "signals" / "src"))

from nq_signals.ranker.walk_forward import walk_forward_validate

# V8 column → NeuralQuant signal name mapping
V8_COLUMN_MAP = {
    "ROE_score":        "quality_percentile",
    "3M_Return_score":  "momentum_percentile",
    "PE_Ratio_score":   "value_percentile",
    "Beta_score":       "low_vol_percentile",   # inverted below
    "HoldingScore":     "holding_percentile",
}

TARGET_COL = "next_quarter_return"
PERIOD_COL = "period"


def load_v8_csv(path: Path) -> pd.DataFrame:
    """Load a V8-format CSV and normalise it for the backtest runner."""
    df = pd.read_csv(path, low_memory=False)

    # --- period column ---
    if "ProcessDate" in df.columns:
        df[PERIOD_COL] = pd.to_datetime(df["ProcessDate"], errors="coerce").dt.to_period("Q").astype(str)
    elif PERIOD_COL not in df.columns:
        raise ValueError(f"CSV {path.name} has no ProcessDate or period column")

    # --- target column ---
    if TARGET_COL not in df.columns:
        if "Return" in df.columns:
            df[TARGET_COL] = pd.to_numeric(df["Return"].replace({"\\N": np.nan}), errors="coerce")
        else:
            raise ValueError(f"CSV {path.name} has no Return or next_quarter_return column")

    # --- map signal columns ---
    for v8_col, nq_col in V8_COLUMN_MAP.items():
        if v8_col in df.columns and nq_col not in df.columns:
            df[nq_col] = pd.to_numeric(df[v8_col], errors="coerce")

    # Invert low_vol (low beta = high score)
    if "low_vol_percentile" in df.columns:
        lo, hi = df["low_vol_percentile"].min(), df["low_vol_percentile"].max()
        if hi != lo:
            df["low_vol_percentile"] = hi - df["low_vol_percentile"] + lo

    return df


def load_historical_data(data_dir: str) -> pd.DataFrame:
    """Load all CSV files from data_dir and concatenate."""
    dfs = []
    for f in Path(data_dir).glob("*.csv"):
        try:
            dfs.append(load_v8_csv(f))
        except Exception as exc:
            print(f"  WARNING: skipping {f.name}: {exc}")
    if not dfs:
        raise FileNotFoundError(f"No usable CSV files found in {data_dir}")
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.dropna(subset=[TARGET_COL, PERIOD_COL])
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description="NeuralQuant walk-forward backtest")
    parser.add_argument("--data-dir",      default="data/backtest",    help="Directory containing historical CSV files")
    parser.add_argument("--output",        default="results/backtest", help="Directory to write results")
    parser.add_argument("--train-periods", type=int, default=12,       help="Number of quarters to train on")
    parser.add_argument("--test-periods",  type=int, default=4,        help="Number of quarters to test per window")
    args = parser.parse_args()

    print(f"NeuralQuant Backtest Runner")
    print(f"{'='*50}")
    print(f"Loading data from: {args.data_dir}")

    df = load_historical_data(args.data_dir)
    periods = sorted(df[PERIOD_COL].unique())
    print(f"Loaded {len(df):,} rows  |  {len(periods)} unique periods")
    print(f"Periods: {periods[0]} to {periods[-1]}")

    # Use whatever signal columns are available
    candidate_features = list(V8_COLUMN_MAP.values())
    available_features = [c for c in candidate_features if c in df.columns]
    if not available_features:
        print("ERROR: No recognised feature columns found. Available:", list(df.columns))
        sys.exit(1)
    print(f"Features: {available_features}")

    min_required = args.train_periods + args.test_periods
    if len(periods) < min_required:
        print(f"\nWARNING: Only {len(periods)} periods available; need {min_required} for "
              f"train={args.train_periods} + test={args.test_periods}.")
        print("Reducing train/test to fit the data...")
        # Scale down proportionally
        ratio = len(periods) / min_required
        args.train_periods = max(2, int(args.train_periods * ratio))
        args.test_periods  = max(1, int(args.test_periods  * ratio))
        print(f"Adjusted: train={args.train_periods}, test={args.test_periods}")

    print(f"\nRunning walk-forward validation  (train={args.train_periods} | test={args.test_periods})")
    results = walk_forward_validate(
        df=df,
        feature_cols=available_features,
        target_col=TARGET_COL,
        period_col=PERIOD_COL,
        train_periods=args.train_periods,
        test_periods=args.test_periods,
    )

    ic: pd.Series = results["ic"]
    icir:     float = results["icir"]
    hit_rate: float = results["hit_rate"]
    ic_mean:  float = results["ic_mean"]
    ic_std:   float = results["ic_std"]

    print(f"\n{'='*50}")
    print("BACKTEST RESULTS")
    print(f"{'='*50}")
    print(f"IC Mean:    {ic_mean:+.4f}  (target: >0.05)")
    print(f"IC Std:     {ic_std:.4f}")
    print(f"ICIR:       {icir:+.4f}  (target: >0.5)")
    print(f"Hit Rate:   {hit_rate:.1%}  (target: >55%)")
    print(f"OOS periods evaluated: {len(ic)}")
    print(f"\nIC by period:")
    for period, val in ic.sort_index().items():
        bar = "#" * int(abs(val) * 20) if not np.isnan(val) else ""
        sign = "+" if val >= 0 else "-"
        print(f"  {period}: {sign}{abs(val):.4f}  {bar}")

    # Save outputs
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    ic_path = out_dir / "ic_by_period.csv"
    ic.to_csv(ic_path, header=["ic"])
    print(f"\n[OK] IC by period saved to {ic_path}")

    summary_path = out_dir / "summary.txt"
    summary_path.write_text(
        f"NeuralQuant Backtest Summary\n"
        f"============================\n"
        f"Periods:    {periods[0]} to {periods[-1]}\n"
        f"Rows:       {len(df):,}\n"
        f"Features:   {available_features}\n"
        f"Train:      {args.train_periods} quarters\n"
        f"Test:       {args.test_periods} quarters\n"
        f"\n"
        f"IC Mean:    {ic_mean:+.4f}\n"
        f"IC Std:     {ic_std:.4f}\n"
        f"ICIR:       {icir:+.4f}\n"
        f"Hit Rate:   {hit_rate:.1%}\n"
        f"OOS qtrs:   {len(ic)}\n"
    )
    print(f"[OK] Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
