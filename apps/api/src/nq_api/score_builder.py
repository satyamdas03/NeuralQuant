# apps/api/src/nq_api/score_builder.py
"""Maps raw SignalEngine output to AIScore schema with explainability."""
from datetime import datetime, timezone
import pandas as pd
from nq_api.schemas import AIScore, SubScores, FeatureDriver

REGIME_LABELS = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}

_FEATURE_DISPLAY = {
    "quality_percentile":        ("Quality composite",   True),
    "momentum_percentile":       ("12-1 Momentum",       True),
    "value_percentile":          ("Value (P/E + P/B)",   True),
    "low_vol_percentile":        ("Low Volatility",      True),
    # NOTE: engine stores 1 - rank_pct, so HIGH value = GOOD (low short interest).
    # higher_is_better MUST be True here — the inversion already happened in the engine.
    "short_interest_percentile": ("Low Short Interest",  True),
    "insider_percentile":        ("Insider Buying (Form 4)", True),
}


def _score_to_1_10(score: float, universe_min: float = 0.35, universe_max: float = 0.65) -> int:
    """
    Map composite score to 1-10.
    Stretches score across the expected universe range (0.35–0.65) so that
    the full integer scale is used rather than everyone clustering at 5.
    """
    clamped = max(universe_min, min(universe_max, score))
    relative = (clamped - universe_min) / (universe_max - universe_min)  # 0–1
    return max(1, min(10, round(relative * 9 + 1)))


def _confidence(row: pd.Series) -> str:
    sub = [
        row.get("quality_percentile", 0.5),
        row.get("momentum_percentile", 0.5),
        row.get("short_interest_percentile", 0.5),
    ]
    spread = max(sub) - min(sub)
    if spread < 0.2:
        return "high"
    if spread < 0.4:
        return "medium"
    return "low"


def build_top_drivers(row: pd.Series) -> list[FeatureDriver]:
    drivers = []
    for col, (name, higher_is_better) in _FEATURE_DISPLAY.items():
        val = row.get(col, 0.5)
        if higher_is_better:
            contribution = (val - 0.5) * 2
        else:
            contribution = (0.5 - val) * 2

        direction = "positive" if contribution > 0.1 else (
            "negative" if contribution < -0.1 else "neutral"
        )
        drivers.append(FeatureDriver(
            name=name,
            contribution=round(contribution, 3),
            value=f"{val:.0%}",
            direction=direction,
        ))

    drivers.sort(key=lambda d: abs(d.contribution), reverse=True)
    return drivers[:5]


def rank_scores_in_universe(result_df: pd.DataFrame) -> pd.Series:
    """
    Return rank-based 1-10 integer scores for all rows.
    Top composite_score in the universe → 10, bottom → 1.
    This spreads scores across the full range instead of everyone scoring 5.
    """
    pct = result_df["composite_score"].rank(pct=True, method="average")
    return (pct * 9 + 1).round().clip(1, 10).astype(int)


def row_to_ai_score(row: pd.Series, market: str, score_1_10_override: int | None = None) -> AIScore:
    regime_id = int(row.get("regime_id", 1))
    composite = float(row["composite_score"])

    return AIScore(
        ticker=str(row["ticker"]),
        market=market,
        composite_score=round(composite, 4),
        score_1_10=score_1_10_override if score_1_10_override is not None else _score_to_1_10(composite),
        regime_id=regime_id,
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        sub_scores=SubScores(
            quality=round(float(row.get("quality_percentile", 0.5)), 3),
            momentum=round(float(row.get("momentum_percentile", 0.5)), 3),
            short_interest=round(float(row.get("short_interest_percentile", 0.5)), 3),
            value=round(float(row.get("value_percentile", 0.5)), 3),
            low_vol=round(float(row.get("low_vol_percentile", 0.5)), 3),
        ),
        top_drivers=build_top_drivers(row),
        confidence=_confidence(row),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
