"""
4-State Hidden Markov Model for market regime detection.
States:
  1 = Risk-On / Trending
  2 = Late Cycle / Overheating
  3 = Stress / Bear
  4 = Recovery
Trained on: VIX, VIX 20d change, SPX vs 200MA, HY spread OAS, ISM PMI
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from sklearn.preprocessing import StandardScaler
from hmmlearn.hmm import GaussianHMM

FEATURE_COLS = ["vix", "vix_20d_change", "spx_vs_200ma", "hy_spread_oas", "ism_pmi"]

# Human-interpretable regime labels based on typical macro patterns
REGIME_LABELS = {
    1: "Risk-On / Trending",
    2: "Late Cycle / Overheating",
    3: "Stress / Bear",
    4: "Recovery",
}

@dataclass
class RegimeState:
    regime_id: int          # 1-4
    label: str
    confidence: float       # Max posterior probability (soft assignment)
    posteriors: np.ndarray  # Full 4-element probability vector
    factor_weights: dict    # Recommended factor weights for this regime

# Factor weights per regime (from spec Section 4.2)
REGIME_WEIGHTS = {
    1: {"momentum": 0.30, "quality": 0.25, "value": 0.10, "low_vol": 0.10, "growth": 0.25},
    2: {"momentum": 0.10, "quality": 0.20, "value": 0.30, "low_vol": 0.15, "growth": 0.25},
    3: {"momentum": 0.05, "quality": 0.30, "value": 0.20, "low_vol": 0.35, "growth": 0.10},
    4: {"momentum": 0.20, "quality": 0.15, "value": 0.30, "low_vol": 0.05, "growth": 0.30},
}

class RegimeDetector:
    def __init__(self, n_regimes: int = 4, random_state: int = 42):
        self.n_regimes = n_regimes
        self._scaler = StandardScaler()
        self._hmm = GaussianHMM(
            n_components=n_regimes,
            covariance_type="full",
            n_iter=100,
            random_state=random_state,
        )
        self._fitted = False
        self._regime_map: dict[int, int] = {}  # HMM state → semantic regime 1-4

    def fit(self, macro_df: pd.DataFrame) -> "RegimeDetector":
        """Fit HMM on historical macro data."""
        X = macro_df[FEATURE_COLS].ffill().fillna(0).values
        X_scaled = self._scaler.fit_transform(X)
        self._hmm.fit(X_scaled)
        self._fitted = True
        self._regime_map = self._assign_semantic_regimes(X_scaled)
        return self

    def _assign_semantic_regimes(self, X_scaled: np.ndarray) -> dict[int, int]:
        """
        Map HMM states (0-indexed) to semantic regime IDs (1-4) based on
        mean VIX and mean SPX-vs-200MA of each state.
        Highest VIX + most negative SPX-vs-200MA → Regime 3 (Stress/Bear)
        Lowest VIX + most positive SPX-vs-200MA → Regime 1 (Risk-On)
        """
        means = self._hmm.means_  # Shape: (n_components, n_features)
        # Feature indices: vix=0, vix_20d_change=1, spx_vs_200ma=2, hy_spread=3, pmi=4
        vix_col = 0
        spx_col = 2

        # Score each state: higher score = more stressed
        stress_scores = means[:, vix_col] - means[:, spx_col]
        ranking = np.argsort(stress_scores)  # Low stress to high stress

        # ranking[0] = least stressed = Risk-On (1)
        # ranking[1] = second least = Recovery (4)
        # ranking[2] = moderate-high stress = Late Cycle (2)
        # ranking[3] = most stressed = Bear (3)
        mapping = {}
        mapping[int(ranking[0])] = 1   # Risk-On
        mapping[int(ranking[1])] = 4   # Recovery
        mapping[int(ranking[2])] = 2   # Late Cycle
        mapping[int(ranking[3])] = 3   # Bear/Stress
        return mapping

    def predict_proba(self, macro_df: pd.DataFrame) -> np.ndarray:
        """Return soft posterior probabilities. Shape: (n_rows, n_regimes)."""
        if not self._fitted:
            raise RuntimeError("Call fit() before predict_proba()")
        X = macro_df[FEATURE_COLS].ffill().fillna(0).values
        X_scaled = self._scaler.transform(X)
        # hmmlearn predict_proba returns shape (n_samples, n_components)
        raw_posteriors = self._hmm.predict_proba(X_scaled)
        # Reorder columns to match semantic regime IDs 1-4
        reordered = np.zeros_like(raw_posteriors)
        for hmm_state, semantic_id in self._regime_map.items():
            reordered[:, semantic_id - 1] = raw_posteriors[:, hmm_state]
        return reordered

    def get_current_state(self, latest_row: pd.DataFrame) -> RegimeState:
        """Get current regime state from the most recent macro observation."""
        posteriors = self.predict_proba(latest_row)[0]
        regime_idx = int(np.argmax(posteriors))  # 0-indexed
        regime_id = regime_idx + 1
        confidence = float(posteriors[regime_idx])
        return RegimeState(
            regime_id=regime_id,
            label=REGIME_LABELS[regime_id],
            confidence=confidence,
            posteriors=posteriors,
            factor_weights=REGIME_WEIGHTS[regime_id],
        )
