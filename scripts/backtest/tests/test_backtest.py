"""
Unit tests for the backtest runner.
Tests the data loading/mapping and the walk-forward integration.
"""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Allow importing scripts without installing
_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_ROOT / "packages" / "signals" / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from backtest.run_backtest import load_v8_csv, PERIOD_COL, TARGET_COL, V8_COLUMN_MAP


# ── helpers ──────────────────────────────────────────────────────────────────

def make_v8_csv(tmp_path: Path, rows: int = 20) -> Path:
    """Create a minimal V8-format CSV for testing."""
    np.random.seed(42)
    quarters = ["2022Q1", "2022Q2", "2022Q3", "2022Q4", "2023Q1"]
    dates = {
        "2022Q1": "01/01/2022", "2022Q2": "04/01/2022",
        "2022Q3": "07/01/2022", "2022Q4": "10/01/2022",
        "2023Q1": "01/01/2023",
    }
    n = rows
    tickers = [f"STOCK{i:02d}" for i in range(n)]
    q_assignment = [quarters[i % len(quarters)] for i in range(n)]

    df = pd.DataFrame({
        "ProcessDate":    [dates[q] for q in q_assignment],
        "NseCode":        tickers,
        "Return":         np.random.uniform(-20, 30, n).tolist(),
        "ROE_score":      np.random.uniform(-1, 1, n).tolist(),
        "3M_Return_score": np.random.uniform(-1, 1, n).tolist(),
        "PE_Ratio_score": np.random.uniform(-1, 1, n).tolist(),
        "Beta_score":     np.random.uniform(-1, 1, n).tolist(),
        "HoldingScore":   np.random.randint(-3, 4, n).tolist(),
    })
    path = tmp_path / "test_v8.csv"
    df.to_csv(path, index=False)
    return path


# ── tests ────────────────────────────────────────────────────────────────────

def test_load_and_map_v8_data(tmp_path):
    """V8 CSV columns are correctly renamed to NeuralQuant signal names."""
    csv_path = make_v8_csv(tmp_path, rows=20)
    df = load_v8_csv(csv_path)

    # period column created
    assert PERIOD_COL in df.columns, "period column must be created from ProcessDate"
    assert df[PERIOD_COL].notna().all(), "All period values must be non-null"

    # target column created
    assert TARGET_COL in df.columns, "next_quarter_return must be mapped from Return"
    assert pd.api.types.is_float_dtype(df[TARGET_COL]), "target must be numeric"

    # signal columns mapped
    expected_signals = list(V8_COLUMN_MAP.values())
    for sig in expected_signals:
        assert sig in df.columns, f"Signal column '{sig}' missing after mapping"


def test_load_handles_mysql_null_in_return(tmp_path):
    r"""\\N values in Return column must be treated as NaN, not crash."""
    df_raw = pd.DataFrame({
        "ProcessDate":    ["01/01/2022", "04/01/2022", "07/01/2022"],
        "NseCode":        ["A", "B", "C"],
        "Return":         [r"\N", "15.3", "-4.2"],
        "ROE_score":      [1.0, 0.5, -0.3],
        "3M_Return_score": [0.2, 0.8, -0.5],
        "PE_Ratio_score": [0.3, -0.1, 0.7],
        "Beta_score":     [-0.5, 0.2, 0.9],
        "HoldingScore":   [1, -1, 2],
    })
    path = tmp_path / "nulls.csv"
    df_raw.to_csv(path, index=False)

    df = load_v8_csv(path)
    # Row with backslash-N should have NaN target
    null_rows = df[df[TARGET_COL].isna()]
    assert len(null_rows) == 1, "Exactly one row should have NaN target (the MySQL-null row)"


def test_backtest_runs_with_synthetic_data():
    """walk_forward_validate runs end-to-end and returns expected keys."""
    from nq_signals.ranker.walk_forward import walk_forward_validate

    np.random.seed(99)
    n_periods = 10
    n_stocks = 15
    records = []
    for p in range(n_periods):
        for _ in range(n_stocks):
            records.append({
                "period": f"2020Q{p+1}" if p < 4 else f"202{p//4}Q{p%4+1}",
                "quality_percentile":  np.random.uniform(0, 1),
                "momentum_percentile": np.random.uniform(0, 1),
                "next_quarter_return": np.random.uniform(-0.2, 0.4),
            })
    df = pd.DataFrame(records)

    results = walk_forward_validate(
        df=df,
        feature_cols=["quality_percentile", "momentum_percentile"],
        target_col="next_quarter_return",
        period_col="period",
        train_periods=4,
        test_periods=2,
    )

    assert isinstance(results, dict)
    for key in ("ic", "icir", "hit_rate", "ic_mean", "ic_std"):
        assert key in results, f"Missing key '{key}' in results"

    assert isinstance(results["ic"], pd.Series)
    assert isinstance(results["icir"], float)
    assert 0.0 <= results["hit_rate"] <= 1.0
