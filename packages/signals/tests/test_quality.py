import pytest
import pandas as pd
from nq_signals.factors.quality import compute_piotroski_score, compute_quality_composite


def make_fundamental(roa=0.08, delta_roa=0.02, cfo=0.12, accruals=-0.03,
                     delta_leverage=-0.05, delta_liquidity=0.1, no_dilution=True,
                     delta_margin=0.02, delta_turnover=0.05) -> dict:
    # Note: the Piotroski "accruals" signal is computed as cfo > roa (CFO > ROA = quality earnings).
    # The `accruals` parameter here is NOT read by compute_piotroski_score — it is kept in the
    # fixture dict for documentation/future use only. The actual accruals test depends on cfo vs roa.
    return {
        "roa": roa, "delta_roa": delta_roa, "cfo": cfo,
        "accruals": accruals, "delta_leverage": delta_leverage,
        "delta_liquidity": delta_liquidity, "shares_issued": 0 if no_dilution else 1000000,
        "delta_gross_margin": delta_margin, "delta_asset_turnover": delta_turnover,
    }


def test_piotroski_score_high_quality():
    f = make_fundamental()
    score = compute_piotroski_score(f)
    assert score >= 7  # High quality firm should score 7-9


def test_piotroski_score_low_quality():
    # roa=-0.01, cfo=-0.05: cfo(-0.05) > roa(-0.01) is False → accruals signal correctly fails
    f = make_fundamental(roa=-0.01, delta_roa=-0.03, cfo=-0.05, accruals=0.08,
                         delta_leverage=0.1, delta_liquidity=-0.2, no_dilution=False,
                         delta_margin=-0.05, delta_turnover=-0.03)
    score = compute_piotroski_score(f)
    assert score <= 3  # Poor quality


def test_quality_composite_cross_sectional_rank():
    """Quality composite should return percentile ranks across a universe."""
    universe = pd.DataFrame([
        {"ticker": "A", "gross_profit_margin": 0.70, "accruals_ratio": -0.05, "piotroski": 8},
        {"ticker": "B", "gross_profit_margin": 0.30, "accruals_ratio":  0.10, "piotroski": 4},
        {"ticker": "C", "gross_profit_margin": 0.50, "accruals_ratio": -0.01, "piotroski": 6},
    ])
    result = compute_quality_composite(universe)
    # A should rank highest (high margin, negative accruals = quality, high piotroski)
    assert result.loc[result["ticker"] == "A", "quality_percentile"].values[0] > \
           result.loc[result["ticker"] == "B", "quality_percentile"].values[0]
