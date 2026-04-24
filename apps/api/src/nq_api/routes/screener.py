# apps/api/src/nq_api/routes/screener.py
import asyncio
import logging

import pandas as pd
from fastapi import APIRouter, Depends

from nq_api.deps import get_signal_engine
from nq_api.schemas import ScreenerRequest, ScreenerResponse
from nq_api.score_builder import row_to_ai_score, rank_scores_in_universe, REGIME_LABELS
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot, fetch_real_macro
from nq_signals.engine import SignalEngine
from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User, TIER_LIMITS
from nq_api.cache import score_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/preview", response_model=ScreenerResponse)
async def screener_preview(market: str = "US", n: int = 8) -> ScreenerResponse:
    """Public, cache-only top-N. No auth, no quota. Used by dashboard preview."""
    try:
        rows = await asyncio.to_thread(score_cache.read_top, market, n=n, max_age_seconds=86400 * 7)
        logger.info("screener_preview: %d rows from cache for market=%s", len(rows), market)
    except Exception as exc:
        logger.exception("screener_preview cache read failed for market=%s", market)
        rows = []
    if not rows:
        # Live-compute fallback when cache is empty (cold start / nightly job missed)
        logger.info("screener_preview: cache empty, falling back to live compute for market=%s", market)
        return await _preview_live_fallback(market, n)
    try:
        macro = fetch_real_macro()
        regime_id = int(macro.regime_id) if hasattr(macro, "regime_id") else 1
    except Exception:
        regime_id = 1
    ai_scores = _cache_rows_to_ai_scores(rows, market, regime_id)
    return ScreenerResponse(
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        regime_id=regime_id,
        results=ai_scores,
        total=len(ai_scores),
    )


async def _preview_live_fallback(market: str, n: int) -> ScreenerResponse:
    """Compute top-N scores live when cache is empty. Slower but always returns data."""
    engine = get_signal_engine()
    tickers = UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"])[:n]
    try:
        snapshot = await asyncio.to_thread(build_real_snapshot, tickers, market)
        if snapshot is None or snapshot.empty:
            return ScreenerResponse(regime_label="Unknown", regime_id=1, results=[], total=0)
        result_df = await asyncio.to_thread(engine.compute, snapshot)
        if result_df is None or result_df.empty:
            return ScreenerResponse(regime_label="Unknown", regime_id=1, results=[], total=0)
        ranked = rank_scores_in_universe(result_df).reset_index(drop=True)
        result_df = result_df.reset_index(drop=True).head(n)
        regime_id = int(result_df["regime_id"].iloc[0]) if "regime_id" in result_df.columns else 1
        ai_scores = [
            row_to_ai_score(row, market, score_1_10_override=int(ranked.iloc[i]))
            for i, (_, row) in enumerate(result_df.iterrows())
        ]
        return ScreenerResponse(
            regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
            regime_id=regime_id,
            results=ai_scores,
            total=len(ai_scores),
        )
    except Exception as exc:
        logger.exception("screener_preview live fallback failed for market=%s", market)
        return ScreenerResponse(regime_label="Unknown", regime_id=1, results=[], total=0)


def _cache_rows_to_ai_scores(rows: list[dict], market: str, regime_id: int) -> list:
    """Build AIScore list from cached rows. Ranks within the batch."""
    if not rows:
        return []
    df = pd.DataFrame(rows)
    df["regime_id"] = regime_id
    ranked = rank_scores_in_universe(df).reset_index(drop=True)
    df = df.reset_index(drop=True)
    return [
        row_to_ai_score(row, market, score_1_10_override=int(ranked.iloc[i]))
        for i, (_, row) in enumerate(df.iterrows())
    ]


@router.post("", response_model=ScreenerResponse)
def run_screener(
    req: ScreenerRequest,
    engine: SignalEngine = Depends(get_signal_engine),
    user: User = Depends(enforce_tier_quota("screener")),
) -> ScreenerResponse:
    # Try cache first for full-universe requests
    custom_tickers = bool(req.tickers)
    if not custom_tickers:
        max_age = TIER_LIMITS[user.tier].screener_refresh_seconds or 86400
        cached = score_cache.read_top(req.market, n=max(100, req.max_results * 3), max_age_seconds=max_age)
        cached = [r for r in cached if (r.get("composite_score") or 0) >= req.min_score]
        if cached:
            # regime: compute cheaply from macro (static across batch)
            try:
                macro = fetch_real_macro()
                regime_id = int(macro.regime_id) if hasattr(macro, "regime_id") else 1
            except Exception:
                regime_id = 1
            cached = cached[: req.max_results]
            ai_scores = _cache_rows_to_ai_scores(cached, req.market, regime_id)
            return ScreenerResponse(
                regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
                regime_id=regime_id,
                results=ai_scores,
                total=len(ai_scores),
            )

    # Live compute fallback (cache miss or custom tickers)
    tickers = req.tickers or UNIVERSE_BY_MARKET.get(req.market, UNIVERSE_BY_MARKET["US"])
    snapshot = build_real_snapshot(tickers, req.market)
    result_df = engine.compute(snapshot)

    filtered = result_df[result_df["composite_score"] >= req.min_score]
    filtered = filtered.sort_values("composite_score", ascending=False)
    ranked_scores = rank_scores_in_universe(filtered).reset_index(drop=True)
    filtered = filtered.reset_index(drop=True).head(req.max_results)

    regime_id = int(result_df["regime_id"].iloc[0]) if not result_df.empty else 1
    ai_scores = [
        row_to_ai_score(row, req.market, score_1_10_override=int(ranked_scores.iloc[i]))
        for i, (_, row) in enumerate(filtered.iterrows())
    ]

    return ScreenerResponse(
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        regime_id=regime_id,
        results=ai_scores,
        total=len(ai_scores),
    )
