# apps/api/src/nq_api/score_builder.py
"""Maps raw SignalEngine output to AIScore schema with explainability."""
import pandas as pd
from nq_api.schemas import AIScore, SubScores, FeatureDriver

REGIME_LABELS = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}

_FEATURE_DISPLAY = {
    "quality_percentile":        ("Quality composite",  True),
    "momentum_percentile":       ("12-1 Momentum",      True),
    "short_interest_percentile": ("Short interest",     False),  # high SI = bearish
}


def _score_to_1_10(score: float) -> int:
    return max(1, min(10, round(score * 9 + 1)))


def _confidence(row: pd.Series) -> str:
    sub = [row.get("quality_percentile", 0.5),
           row.get("momentum_percentile", 0.5)]
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


def row_to_ai_score(row: pd.Series, market: str) -> AIScore:
    from datetime import datetime, timezone
    regime_id = int(row.get("regime_id", 1))
    composite = float(row["composite_score"])

    return AIScore(
        ticker=str(row["ticker"]),
        market=market,
        composite_score=round(composite, 4),
        score_1_10=_score_to_1_10(composite),
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
