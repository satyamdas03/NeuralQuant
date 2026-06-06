# apps/api/src/nq_api/score_builder.py
"""Maps raw SignalEngine output to AIScore schema with explainability.

Since v4.1: QuantFactor enrichment blend — 60% existing 5-factor composite,
40% QuantFactor quintile composite (normalized -16..+16 → 0..10).
"""
from datetime import datetime, timezone
import logging
import math
import os

import pandas as pd
from nq_api.schemas import AIScore, SubScores, FeatureDriver, AnjaliScores

logger = logging.getLogger(__name__)

REGIME_LABELS = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}


def _safe_float(v, default: float = 0.0) -> float:
    """Coerce to finite float; NaN/None/inf → default. Prevents NaN leaking into Supabase writes."""
    try:
        if v is None:
            return default
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return default
        if pd.isna(v):
            return default
        fv = float(v)
        return fv if math.isfinite(fv) else default
    except (TypeError, ValueError):
        return default

_FEATURE_DISPLAY = {
    "quality_percentile":        ("Quality composite",   True),
    "momentum_percentile":       ("12-1 Momentum",       True),
    "value_percentile":          ("Value (P/E + P/B)",   True),
    "low_vol_percentile":        ("Low Volatility",      True),
    "growth_percentile":         ("Revenue Growth YoY",  True),
    # NOTE: engine stores 1 - rank_pct, so HIGH value = GOOD (low short interest).
    # higher_is_better MUST be True here — the inversion already happened in the engine.
    "short_interest_percentile": ("Low Short Interest",  True),
    "insider_percentile":        ("Insider Buying (Form 4)", True),
}


def _score_to_1_10(score: float, universe_min: float = 0.30, universe_max: float = 0.75) -> int:
    """
    Map composite score to 1-10.
    Stretches score across the expected universe range (0.30–0.75) so that
    the full integer scale is used rather than everyone clustering at 5.
    Range updated after BUG-001 fix (growth weight renormalization) which raised
    typical composites from 0.35-0.57 → 0.32-0.75.
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


# ---------------------------------------------------------------------------
# QuantFactor enrichment blend
# ---------------------------------------------------------------------------

_ANJALI_BLEND_WEIGHT = 0.4  # 60% existing 5-factor, 40% QuantFactor composite
_ANJALI_CACHE: dict[str, dict] = {}  # Simple in-memory cache
_ANJALI_CACHE_MAX_AGE = 3600  # 1 hour in seconds
_ANJALI_CACHE_LOADED_AT: float = 0


def _supabase_rest(table: str, method: str = "GET", query: dict | None = None, body=None):
    """Minimal Supabase REST call for QuantFactor data lookup."""
    import requests
    from nq_api.cache.score_cache import _sanitize_floats
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    # Sanitize body before JSON serialization (NaN/Inf → None)
    if body is not None:
        if isinstance(body, list):
            body = [_sanitize_floats(item) if isinstance(item, dict) else item for item in body]
        elif isinstance(body, dict):
            body = _sanitize_floats(body)
    try:
        resp = requests.request(method, endpoint, headers=headers, params=query, json=body, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug(f"Anjali Supabase lookup failed: {e}")
        return None


def _load_anjali_cache():
    """Load all QuantFactor enrichment data into memory cache."""
    global _ANJALI_CACHE, _ANJALI_CACHE_LOADED_AT
    import time

    now = time.time()
    if now - _ANJALI_CACHE_LOADED_AT < _ANJALI_CACHE_MAX_AGE and _ANJALI_CACHE:
        return

    data = _supabase_rest(
        "anjali_enrichment",
        method="GET",
        query={"select": "ticker,market,composite_anjali_score,growth_score,return_score,valuation_score,risk_score,g_score,risk_eff_score,irs_raw,irs_pct,future_pe,future_peg,loss_profit_yoy,loss_profit_ttm,loss_profit_qoq"},
    )
    if data and isinstance(data, list):
        _ANJALI_CACHE = {}
        for row in data:
            key = f"{row.get('ticker', '')}:{row.get('market', 'US')}"
            _ANJALI_CACHE[key] = row
        _ANJALI_CACHE_LOADED_AT = now
        logger.debug(f"Anjali cache loaded: {len(_ANJALI_CACHE)} rows")


def get_anjali_enrichment(ticker: str, market: str) -> dict | None:
    """Look up QuantFactor enrichment data for a ticker.

    Returns dict with QuantFactor scores, or None if not available.
    """
    _load_anjali_cache()
    key = f"{ticker}:{market}"
    row = _ANJALI_CACHE.get(key)
    if not row:
        # Try bare ticker (without .NS suffix for Indian stocks)
        bare = ticker.replace(".NS", "").replace(".BO", "")
        row = _ANJALI_CACHE.get(f"{bare}:{market}")
    return row if row else None


def blend_anjali_score(composite: float, anjali_data: dict | None) -> tuple[float, bool]:
    """Blend existing 5-factor composite with QuantFactor quintile composite.

    QuantFactor composite ranges from -16 to +16. Normalized to 0-10 scale:
        anjali_10 = (composite_anjali_score + 16) / 32 * 10

    Blend: 60% existing, 40% QuantFactor (if QuantFactor data available).

    Returns:
        (blended_composite, anjali_available) tuple.
    """
    if not anjali_data or anjali_data.get("composite_anjali_score") is None:
        return composite, False

    anjali_raw = float(anjali_data["composite_anjali_score"])
    # Normalize: -16..+16 → 0..10
    anjali_10 = (anjali_raw + 16) / 32 * 10
    anjali_10 = max(0, min(10, anjali_10))  # clamp

    # Normalize existing composite to 0-10 scale
    existing_10 = _score_to_1_10(composite)

    # Blend
    blended_10 = existing_10 * (1 - _ANJALI_BLEND_WEIGHT) + anjali_10 * _ANJALI_BLEND_WEIGHT
    blended_10 = max(1, min(10, round(blended_10, 1)))

    # Convert back to 0-1 composite scale
    blended_composite = (blended_10 - 1) / 9  # 1→0, 10→1
    return round(blended_composite, 4), True


def row_to_ai_score(row: pd.Series, market: str, score_1_10_override: int | None = None) -> AIScore:
    regime_id = int(row.get("regime_id", 1) or 1)
    composite = _safe_float(row.get("composite_score", 0.0), 0.0)

    # Blend with QuantFactor if available
    anjali_data = get_anjali_enrichment(str(row["ticker"]), market)
    composite, anjali_available = blend_anjali_score(composite, anjali_data)

    # Recalculate score_1_10 if QuantFactor blend changed composite
    if anjali_available and score_1_10_override is None:
        score_1_10_override = _score_to_1_10(composite)

    # Build QuantFactor scores if available
    anjali_scores = None
    if anjali_data and anjali_available:
        val_score = anjali_data.get("valuation_score")
        anjali_scores = AnjaliScores(
            growth_score=anjali_data.get("growth_score"),
            return_score=anjali_data.get("return_score"),
            valuation_score=val_score,
            risk_score=anjali_data.get("risk_score"),
            composite=anjali_data.get("composite_anjali_score"),
            g_score=anjali_data.get("g_score"),
            risk_eff_score=anjali_data.get("risk_eff_score"),
            irs_raw=anjali_data.get("irs_raw"),
            irs_pct=anjali_data.get("irs_pct"),
            is_loss_making=bool(
                anjali_data.get("loss_profit_yoy") or anjali_data.get("loss_profit_ttm") or anjali_data.get("loss_profit_qoq")
            ),
            valuation_sweet_spot=0.5 <= (val_score or 0) <= 1.5 if val_score is not None else False,
        )

    return AIScore(
        ticker=str(row["ticker"]),
        market=market,
        composite_score=round(composite, 4),
        score_1_10=score_1_10_override if score_1_10_override is not None else _score_to_1_10(composite),
        regime_id=regime_id,
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        sub_scores=SubScores(
            quality=round(_safe_float(row.get("quality_percentile", 0.5), 0.5), 3),
            momentum=round(_safe_float(row.get("momentum_percentile", 0.5), 0.5), 3),
            short_interest=round(_safe_float(row.get("short_interest_percentile", 0.5), 0.5), 3),
            value=round(_safe_float(row.get("value_percentile", 0.5), 0.5), 3),
            low_vol=round(_safe_float(row.get("low_vol_percentile", 0.5), 0.5), 3),
            growth=round(_safe_float(row.get("growth_percentile", 0.5), 0.5), 3),
        ),
        top_drivers=build_top_drivers(row),
        confidence=_confidence(row),
        last_updated=datetime.now(timezone.utc).isoformat(),
        anjali=anjali_scores,
    )
