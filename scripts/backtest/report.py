"""
Backtest report generator.
Reads the IC CSV output from run_backtest.py and prints a formatted summary.

Usage:
    uv run python scripts/backtest/report.py --results results/backtest
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def print_separator(char="=", width=60) -> None:
    print(char * width)


def print_ic_table(ic: pd.Series) -> None:
    """Print a formatted IC by-period table with rolling mean."""
    print(f"\n{'Period':<12} {'IC':>8} {'Rolling-4':>10} {'Signal':>8}")
    print_separator("-", 42)

    values = ic.sort_index()
    for i, (period, val) in enumerate(values.items()):
        # Rolling mean over last 4 periods
        window = values.iloc[max(0, i - 3): i + 1]
        rolling = window.mean()

        # Visual signal
        if np.isnan(val):
            signal = "  ?"
        elif val > 0.10:
            signal = " ++"
        elif val > 0.05:
            signal = "  +"
        elif val > 0:
            signal = "  ~"
        elif val > -0.05:
            signal = "  -"
        else:
            signal = " --"

        rolling_str = f"{rolling:+.4f}" if not np.isnan(rolling) else "      -"
        val_str = f"{val:+.4f}" if not np.isnan(val) else "      -"
        print(f"{str(period):<12} {val_str:>8} {rolling_str:>10} {signal:>8}")


def main() -> None:
    parser = argparse.ArgumentParser(description="NeuralQuant backtest report viewer")
    parser.add_argument("--results", default="results/backtest", help="Directory with backtest outputs")
    args = parser.parse_args()

    results_dir = Path(args.results)

    # Load IC series
    ic_path = results_dir / "ic_by_period.csv"
    if not ic_path.exists():
        print(f"ERROR: {ic_path} not found. Run run_backtest.py first.")
        return

    ic = pd.read_csv(ic_path, index_col=0, squeeze=False).iloc[:, 0]
    ic.name = "ic"

    # Load summary if available
    summary_path = results_dir / "summary.txt"

    print_separator()
    print("  NeuralQuant — Backtest Report")
    print_separator()

    if summary_path.exists():
        print(summary_path.read_text())
        print_separator()

    print_ic_table(ic)

    print_separator()
    print(f"\nKey Statistics:")
    print(f"  IC Mean:  {ic.mean():+.4f}   (industry benchmark: >0.05)")
    print(f"  IC Std:   {ic.std():.4f}")
    icir = ic.mean() / ic.std() if ic.std() > 0 else 0.0
    print(f"  ICIR:     {icir:+.4f}   (world-class: >1.0)")
    print(f"  Hit Rate: {(ic > 0).mean():.1%}   (target: >55%)")
    print(f"  Best Q:   {ic.max():+.4f}  ({ic.idxmax()})")
    print(f"  Worst Q:  {ic.min():+.4f}  ({ic.idxmin()})")
    print()


if __name__ == "__main__":
    main()
