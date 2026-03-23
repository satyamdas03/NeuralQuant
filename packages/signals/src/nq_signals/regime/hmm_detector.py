"""
4-State Hidden Markov Model for market regime detection.
States:
  1 = Risk-On / Trending
  2 = Late Cycle / Overheating
  3 = Stress / Bear
  4 = Recovery
Trained on: VIX, VIX 20d change, SPX vs 200MA, HY spread OAS, ISM PMI
"""
import warnings
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
        if not self._hmm.monitor_.converged:
            warnings.warn(
                f"GaussianHMM did not converge after {self._hmm.n_iter} iterations. "
                "Regime assignments may be unreliable. Consider increasing n_iter or "
                "providing more training data.",
                UserWarning,
                stacklevel=2,
            )
        self._fitted = True
        self._regime_map = self._assign_semantic_regimes(X_scaled)
        return self

    def _assign_semantic_regimes(self, X_scaled: np.ndarray) -> dict[int, int]:
        """
        Map HMM states (0-indexed) to semantic regime IDs (1-4).

        Outer anchors (robust):
          - Lowest stress (VIX - SPX_vs_200MA) → Regime 1 (Risk-On)
          - Highest stress → Regime 3 (Stress/Bear)

        Middle states distinguished by PMI:
          - Higher PMI among middle two → Regime 4 (Recovery, PMI rising)
          - Lower PMI among middle two → Regime 2 (Late Cycle, PMI softening)
        """
        means = self._hmm.means_  # Shape: (n_components, n_features)
        vix_col = 0      # Index in FEATURE_COLS
        spx_col = 2      # Index in FEATURE_COLS
        pmi_col = 4      # Index in FEATURE_COLS

        # Primary stress score for outer anchor assignment
        stress_scores = means[:, vix_col] - means[:, spx_col]
        ranking = np.argsort(stress_scores)  # Low stress → high stress (4 indices)

        mapping: dict[int, int] = {}
        mapping[int(ranking[0])] = 1   # Least stressed → Risk-On
        mapping[int(ranking[3])] = 3   # Most stressed → Stress/Bear

        # Differentiate the two middle states by PMI
        mid_states = [int(ranking[1]), int(ranking[2])]
        pmi_values = [means[s, pmi_col] for s in mid_states]
        if pmi_values[0] >= pmi_values[1]:
            # mid_states[0] has higher PMI → Recovery
            mapping[mid_states[0]] = 4  # Recovery
            mapping[mid_states[1]] = 2  # Late Cycle
        else:
            mapping[mid_states[0]] = 2  # Late Cycle
            mapping[mid_states[1]] = 4  # Recovery

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

    def get_current_state(self, latest_row: pd.DataFrame,
                          context_rows: Optional[pd.DataFrame] = None) -> RegimeState:
        """
        Get current regime state from the most recent macro observation.

        Args:
            latest_row: Single-row DataFrame with current macro values.
            context_rows: Optional historical rows to provide sequence context.
                          If provided, posteriors are computed on the full sequence
                          and only the last row's posterior is returned.
                          Recommended: provide last 20+ rows for meaningful posteriors.
        """
        if context_rows is not None and len(context_rows) > 0:
            # Use full sequence for posteriors, take last row
            full_df = pd.concat([context_rows, latest_row], ignore_index=True)
            posteriors = self.predict_proba(full_df)[-1]
        else:
            # Single-row: posteriors are emission-weighted priors only
            # Still useful as a rough signal but confidence will be lower
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
