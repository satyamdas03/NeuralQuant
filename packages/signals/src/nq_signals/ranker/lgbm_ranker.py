"""
LightGBM LambdaRank — cross-sectional stock ranking model.
Framing: learning-to-rank (not regression) — rank stocks by expected return.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb


class SignalRanker:
    def __init__(self, num_leaves: int = 31, n_estimators: int = 200,
                 learning_rate: float = 0.05):
        self.params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [5, 10],
            "num_leaves": num_leaves,
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "min_child_samples": 5,
            "verbose": -1,
        }
        self._model: lgb.LGBMRanker | None = None
        self._feature_cols: list[str] = []

    def fit(self, df: pd.DataFrame, feature_cols: list[str],
            target_col: str, group_col: str) -> "SignalRanker":
        """
        Train LambdaRank on panel data.
        df: DataFrame with feature_cols, target_col (returns), group_col (period/quarter)
        """
        self._feature_cols = feature_cols
        # Sort by group to ensure consistent group sizes
        df = df.sort_values(group_col).copy()
        groups = df.groupby(group_col, sort=True)
        group_sizes = [len(g) for _, g in groups]

        # Convert continuous returns to relevance grades (0-3) for LambdaRank
        # LightGBM lambdarank requires non-negative integer labels
        for period, g_idx in groups.groups.items():
            q = df.loc[g_idx, target_col].rank(pct=True)
            df.loc[g_idx, "_relevance"] = (q * 3).astype(int).clip(0, 3)

        X = df[feature_cols].fillna(0.5).values
        y = df["_relevance"].values.astype(int)

        self._model = lgb.LGBMRanker(**self.params)
        self._model.fit(X, y, group=group_sizes)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return ranking scores. Higher = better expected return."""
        if self._model is None:
            raise RuntimeError("Call fit() first")
        return self._model.predict(X[self._feature_cols].fillna(0.5).values)

    @property
    def feature_importances(self) -> dict[str, float]:
        if self._model is None:
            return {}
        return dict(zip(self._feature_cols,
                        self._model.feature_importances_.tolist()))
