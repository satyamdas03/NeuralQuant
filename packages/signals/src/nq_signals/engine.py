"""
Signal Engine Orchestrator — computes all 10 signals and produces a ranked universe.
This is the Layer 2 workhorse that feeds the Layer 3 agent system.
"""
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np

from .factors.quality import compute_quality_composite
from .factors.momentum import compute_momentum_cross_sectional, apply_crash_protection
from .factors.growth import compute_growth_cross_sectional
from .regime.hmm_detector import RegimeDetector, RegimeState, REGIME_WEIGHTS

# Fixed allocations for regime-invariant signals. Pulled from the remaining
# regime budget so the composite weights always sum to exactly 1.0:
#   regime_budget * sum(regime_weights) + SHORT_INT + INSIDER = 0.85 * 1.0 + 0.10 + 0.05 = 1.00
SHORT_INT_WEIGHT = 0.10
INSIDER_WEIGHT = 0.05

# IN market: delivery_pct replaces short_interest as a liquidity conviction signal
DELIVERY_WEIGHT = 0.10


@dataclass
class UniverseSnapshot:
    tickers: list[str]
    market: str          # "US" | "IN" | "GLOBAL"
    fundamentals: pd.DataFrame
    macro: object        # MacroSnapshot-like object


class SignalEngine:
    def __init__(self, regime_detector: Optional[RegimeDetector] = None,
                 regime_detector_in=None):
        self._regime_detector = regime_detector
        self._regime_detector_in = regime_detector_in

    def _get_regime(self, macro, market: str = "US") -> RegimeState:
        """Get current market regime from macro snapshot."""
        if self._regime_detector is None or not self._regime_detector._fitted:
            return RegimeState(
                regime_id=1, label="Risk-On",
                confidence=0.5,
                posteriors=np.array([0.5, 0.2, 0.2, 0.1]),
                factor_weights=REGIME_WEIGHTS[1],
            )

        if market == "IN":
            # Use India HMM if available, fall back to VIX heuristic
            if self._regime_detector_in is not None:
                macro_row = pd.DataFrame([{
                    "india_vix": float(getattr(macro, "india_vix", 15.0) or 15.0),
                    "india_vix_20d_chg": float(getattr(macro, "india_vix_20d_chg", 0.0) or 0.0),
                    "nifty_vs_200ma": float(getattr(macro, "nifty_vs_200ma", 0.0) or 0.0),
                    "inr_usd_1m_chg": float(getattr(macro, "inr_usd_1m_chg", 0.0) or 0.0),
                    "nifty_1m_return": float(getattr(macro, "nifty_return_1m", 0.0) or 0.0),
                }])
                return self._regime_detector_in.get_current_state(macro_row)

            # Fallback: hardcoded India VIX thresholds
            ivix = float(getattr(macro, "india_vix", 15.0) or 15.0)
            nifty_200ma = float(getattr(macro, "nifty_vs_200ma", 0.0) or 0.0)
            if ivix > 25 or nifty_200ma < -0.08:
                return RegimeState(
                    regime_id=3, label="Bear",
                    confidence=0.6,
                    posteriors=np.array([0.1, 0.2, 0.6, 0.1]),
                    factor_weights=REGIME_WEIGHTS[3],
                )
            if ivix > 18 or nifty_200ma < -0.02:
                return RegimeState(
                    regime_id=2, label="Late-Cycle",
                    confidence=0.5,
                    posteriors=np.array([0.2, 0.5, 0.2, 0.1]),
                    factor_weights=REGIME_WEIGHTS[2],
                )
            return RegimeState(
                regime_id=1, label="Risk-On",
                confidence=0.6,
                posteriors=np.array([0.6, 0.2, 0.1, 0.1]),
                factor_weights=REGIME_WEIGHTS[1],
            )

        # US market: use HMM detector
        macro_row = pd.DataFrame([{
            "vix": macro.vix, "vix_20d_change": 0.0,
            "spx_vs_200ma": macro.spx_vs_200ma,
            "hy_spread_oas": macro.hy_spread_oas,
            "ism_pmi": macro.ism_pmi,
        }])
        return self._regime_detector.get_current_state(macro_row)

    def compute(self, snapshot: UniverseSnapshot) -> pd.DataFrame:
        """
        Compute all signals and return regime-weighted composite scores.
        Returns DataFrame sorted by composite_score descending.
        """
        df = snapshot.fundamentals.copy()
        regime = self._get_regime(snapshot.macro, snapshot.market)

        # Crash protection uses market-appropriate index
        if snapshot.market == "IN":
            spx_ret = float(getattr(snapshot.macro, "nifty_return_1m", 0.0) or 0.0)
            spx_200ma = float(getattr(snapshot.macro, "nifty_vs_200ma", 0.0) or 0.0)
        else:
            spx_ret = float(getattr(snapshot.macro, "spx_return_1m", 0.0) or 0.0)
            spx_200ma = float(getattr(snapshot.macro, "spx_vs_200ma", 0.0) or 0.0)

        crash_flag = apply_crash_protection(
            spx_return_1m=spx_ret,
            spx_vs_200ma=spx_200ma,
        )

        # 1. Quality composite
        df = compute_quality_composite(df)

        # 2. Momentum — requires momentum_raw column
        df = compute_momentum_cross_sectional(df, crash_flag=crash_flag)

        # 3. Growth — revenue growth YoY cross-sectional percentile
        df = compute_growth_cross_sectional(df)

        # 3. Short interest (lower short interest = better) — US only
        if "short_interest_pct" in df.columns and snapshot.market != "IN":
            si_col = pd.to_numeric(df["short_interest_pct"], errors="coerce")
            df["short_interest_percentile"] = 1.0 - si_col.rank(pct=True)
        else:
            df["short_interest_percentile"] = 0.5

        # 3b. IN market: delivery_pct as a liquidity conviction signal
        # Higher delivery % = stronger institutional conviction
        if "delivery_pct" in df.columns and df["delivery_pct"].notna().any():
            del_col = pd.to_numeric(df["delivery_pct"], errors="coerce")
            valid = del_col.dropna()
            if len(valid) > 5:
                df["delivery_percentile"] = del_col.rank(pct=True, na_option="keep").fillna(0.5)
            else:
                df["delivery_percentile"] = 0.5
        else:
            df["delivery_percentile"] = 0.5

        # Regime-weighted composite score
        w = regime.factor_weights
        quality = df.get("quality_percentile", pd.Series(0.5, index=df.index))
        momentum = df.get("momentum_percentile", pd.Series(0.5, index=df.index))
        short_int = df.get("short_interest_percentile", pd.Series(0.5, index=df.index))
        delivery = df.get("delivery_percentile", pd.Series(0.5, index=df.index))

        # Scale regime weights to fill the remaining budget
        if snapshot.market == "IN":
            # IN: delivery_pct replaces short_interest in the budget
            regime_budget = 1.0 - DELIVERY_WEIGHT - INSIDER_WEIGHT  # 0.85
        else:
            regime_budget = 1.0 - SHORT_INT_WEIGHT - INSIDER_WEIGHT  # 0.85

        value    = df.get("value_percentile",    pd.Series(0.5, index=df.index))
        low_vol  = df.get("low_vol_percentile",  pd.Series(0.5, index=df.index))
        insider  = df.get("insider_percentile",  pd.Series(0.5, index=df.index))

        # All 5 regime-weighted factors now active (growth was previously defined
        # but never computed — its weight was silently redistributed).
        _active_keys = ["quality", "momentum", "value", "low_vol", "growth"]
        _used_w = sum(w.get(k, 0.0) for k in _active_keys)
        _scale = regime_budget / _used_w if _used_w > 0 else regime_budget

        growth = df.get("growth_percentile", pd.Series(0.5, index=df.index))

        if snapshot.market == "IN":
            df["composite_score"] = (
                quality   * w.get("quality",   0.25) * _scale +
                momentum  * w.get("momentum",  0.25) * _scale +
                delivery  * DELIVERY_WEIGHT +
                insider   * INSIDER_WEIGHT +
                value     * w.get("value",     0.10) * _scale +
                low_vol   * w.get("low_vol",   0.15) * _scale +
                growth    * w.get("growth",    0.25) * _scale
            )
        else:
            df["composite_score"] = (
                quality   * w.get("quality",   0.25) * _scale +
                momentum  * w.get("momentum",  0.25) * _scale +
                short_int * SHORT_INT_WEIGHT +
                insider   * INSIDER_WEIGHT +
                value     * w.get("value",     0.10) * _scale +
                low_vol   * w.get("low_vol",   0.15) * _scale +
                growth    * w.get("growth",    0.25) * _scale
            )

        df["regime_id"] = regime.regime_id
        df["regime_confidence"] = regime.confidence

        return df.sort_values("composite_score", ascending=False).reset_index(drop=True)