# apps/api/src/nq_api/routes/screener.py
import asyncio
import logging
from typing import TYPE_CHECKING, Any

import pandas as pd
from fastapi import APIRouter, Depends

from nq_api.deps import get_signal_engine
from nq_api.schemas import ScreenerRequest, ScreenerResponse
from nq_api.score_builder import row_to_ai_score, rank_scores_in_universe, REGIME_LABELS
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot, fetch_real_macro
from nq_api.auth.rate_limit import enforce_guest_quota
from nq_api.auth.models import User, TIER_LIMITS
from nq_api.cache import score_cache

logger = logging.getLogger(__name__)

router = APIRouter()

PRESETS = [
    {"id": "momentum_breakout", "name": "Momentum Breakout", "description": "Strong upward momentum stocks",
     "filters": {"min_score": 7, "min_momentum": 70}, "icon": "TrendingUp"},
    {"id": "value_play", "name": "Value Play", "description": "Undervalued quality stocks",
     "filters": {"min_score": 5, "min_quality": 70}, "icon": "DollarSign"},
    {"id": "dividend_income", "name": "Dividend Income", "description": "High-quality low-volatility stocks",
     "filters": {"min_quality": 60, "min_score": 5, "min_low_vol": 60}, "icon": "Banknote"},
    {"id": "quality_compound", "name": "Quality Compound", "description": "Long-term compounders",
     "filters": {"min_quality": 80, "min_score": 7}, "icon": "Gem"},
    {"id": "contrarian_bet", "name": "Contrarian Bet", "description": "Beaten down but fundamentally sound",
     "filters": {"min_quality": 50, "max_momentum": 40}, "icon": "RotateCcw"},
]


@router.get("/presets")
def get_screener_presets() -> dict:
    return {"presets": PRESETS}


def _get_live_regime_id(market: str = "US") -> int:
    """Detect current regime via SignalEngine._get_regime().
    BUG-004 fix: _LiveMacro has no regime_id field so hasattr() always fails.
    Use the engine directly instead of reading a non-existent attribute."""
    try:
        macro = fetch_real_macro()
        engine = get_signal_engine()
        regime = engine._get_regime(macro, market)
        return regime.regime_id
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return 1


@router.get("/preview", response_model=ScreenerResponse)
async def screener_preview(market: str = "US", n: int = 8) -> ScreenerResponse:
    """Public, cache-only top-N. No auth, no quota. Used by dashboard preview."""
    rows = []
    cache_age = "fresh"
    try:
        # Tier 1: fresh cache (≤5 min)
        rows = await asyncio.to_thread(score_cache.read_top, market, n=n, max_age_seconds=300)
        if not rows:
            # Tier 2: stale cache (≤24 h) — nightly GHA data, better than timeout
            rows = await asyncio.to_thread(score_cache.read_top, market, n=n, max_age_seconds=86400)
            if rows:
                cache_age = "stale"
                logger.info("screener_preview: serving stale cache (>%5min) for market=%s", market)
        if not rows:
            # Tier 3: any age — better than empty response
            rows = await asyncio.to_thread(score_cache.read_top, market, n=n, max_age_seconds=999999999)
            if rows:
                cache_age = "very_old"
                logger.warning("screener_preview: serving very old cache for market=%s", market)
        if rows:
            logger.info("screener_preview: %d rows from cache for market=%s", len(rows), market)
    except Exception as exc:
        logger.exception("screener_preview cache read failed for market=%s", market)

    # If cache is very old (>24h), try live compute first before serving stale data.
    # On success we get fresh scores; on failure we fall back to the old cache.
    if cache_age == "very_old" and rows:
        import os
        on_render = bool(os.environ.get("RENDER"))
        live_n = min(n, 5) if on_render else min(n, 8)
        timeout_seconds = 15.0 if on_render else 25.0
        logger.info("screener_preview: cache very old, attempting live compute for market=%s render=%s tickers=%d timeout=%.0fs", market, on_render, live_n, timeout_seconds)
        live_result = await _preview_live_fallback(market, live_n, timeout_seconds)
        if live_result and live_result.total > 0:
            logger.info("screener_preview: live compute succeeded for market=%s, returning fresh data", market)
            return live_result
        logger.warning("screener_preview: live compute failed for market=%s, falling back to old cache", market)

    if not rows:
        # Tier 4: live compute (last resort, strict timeout)
        import os
        on_render = bool(os.environ.get("RENDER"))
        live_n = min(n, 5) if on_render else min(n, 8)
        timeout_seconds = 15.0 if on_render else 25.0
        logger.info("screener_preview: cache empty, falling back to live compute for market=%s render=%s tickers=%d timeout=%.0fs", market, on_render, live_n, timeout_seconds)
        return await _preview_live_fallback(market, live_n, timeout_seconds)

    regime_id = _get_live_regime_id(market)
    ai_scores = _cache_rows_to_ai_scores(rows, market, regime_id)
    return ScreenerResponse(
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        regime_id=regime_id,
        results=ai_scores,
        total=len(ai_scores),
    )


async def _preview_live_fallback(market: str, n: int, timeout: float = 25.0) -> ScreenerResponse:
    """Compute top-N scores live when cache is empty. Slower but always returns data."""
    engine = get_signal_engine()
    tickers = UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"])[:n]
    try:
        snapshot = await asyncio.wait_for(
            asyncio.to_thread(build_real_snapshot, tickers, market),
            timeout=timeout,
        )
        if snapshot is None or snapshot.fundamentals.empty:
            return ScreenerResponse(regime_label="Unknown", regime_id=1, results=[], total=0)
        result_df = await asyncio.wait_for(
            asyncio.to_thread(engine.compute, snapshot),
            timeout=15,
        )
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
    except asyncio.TimeoutError:
        logger.warning("screener_preview live fallback timed out for market=%s", market)
        return ScreenerResponse(regime_label="Unknown", regime_id=1, results=[], total=0)
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


def _apply_preset_filters(scores: list, req: ScreenerRequest) -> list:
    """Filter AIScore results by preset sub-score thresholds."""
    # Apply preset defaults if preset specified
    preset_filters = {}
    if req.preset:
        preset_match = next((p for p in PRESETS if p["id"] == req.preset), None)
        if preset_match:
            preset_filters = preset_match["filters"]

    # Merge: explicit request params override preset defaults
    min_momentum = req.min_momentum if req.min_momentum is not None else preset_filters.get("min_momentum")
    min_quality = req.min_quality if req.min_quality is not None else preset_filters.get("min_quality")
    min_low_vol = req.min_low_vol if req.min_low_vol is not None else preset_filters.get("min_low_vol")
    max_momentum = req.max_momentum if req.max_momentum is not None else preset_filters.get("max_momentum")

    filtered = scores
    if min_momentum is not None:
        filtered = [s for s in filtered if s.sub_scores.momentum * 100 >= min_momentum]
    if max_momentum is not None:
        filtered = [s for s in filtered if s.sub_scores.momentum * 100 <= max_momentum]
    if min_quality is not None:
        filtered = [s for s in filtered if s.sub_scores.quality * 100 >= min_quality]
    if min_low_vol is not None:
        filtered = [s for s in filtered if s.sub_scores.low_vol * 100 >= min_low_vol]
    return filtered


@router.get("", response_model=ScreenerResponse)
async def run_screener_get(
    market: str = "US",
    max_results: int = 20,
    min_score: float = 5.0,
    preset: str | None = None,
    engine: Any = Depends(get_signal_engine),
    user: User | None = Depends(enforce_guest_quota("screener")),
) -> ScreenerResponse:
    """GET wrapper for screener (bots / preloads often hit GET instead of POST)."""
    req = ScreenerRequest(
        market=market,
        max_results=max_results,
        min_score=min_score,
        preset=preset,
    )
    return await run_screener(req, engine, user)


@router.post("", response_model=ScreenerResponse)
async def run_screener(
    req: ScreenerRequest,
    engine: Any = Depends(get_signal_engine),
    user: User | None = Depends(enforce_guest_quota("screener")),
) -> ScreenerResponse:
    # Try cache first for full-universe requests
    custom_tickers = bool(req.tickers)
    if not custom_tickers:
        # Tiered cache: fresh → stale → live
        tier_age = TIER_LIMITS[user.tier if user else "free"].screener_refresh_seconds or 86400
        # Development phase: use aggressive cache (60s) for all tiers
        if tier_age > 60:
            tier_age = 60
        cached = await asyncio.to_thread(score_cache.read_top, req.market, n=max(100, req.max_results * 3), max_age_seconds=tier_age)
        if not cached:
            # Broader fallback — stale cache better than live compute timeout
            cached = await asyncio.to_thread(score_cache.read_top, req.market, n=max(100, req.max_results * 3), max_age_seconds=86400)
        cached = [r for r in cached if (r.get("composite_score") or 0) >= req.min_score]
        if cached:
            # regime: compute cheaply from macro (static across batch)
            regime_id = _get_live_regime_id(req.market)
            cached = cached[: req.max_results]
            ai_scores = _cache_rows_to_ai_scores(cached, req.market, regime_id)
            ai_scores = _apply_preset_filters(ai_scores, req)
            return ScreenerResponse(
                regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
                regime_id=regime_id,
                results=ai_scores,
                total=len(ai_scores),
            )

    # Live compute fallback (cache miss or custom tickers) — hard 20s timeout
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_screener_sync, req, engine),
            timeout=20.0,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("run_screener timed out for market=%s after 20s", req.market)
        # Return partial: try serving whatever cache we have, even if stale
        try:
            cached_fallback = await asyncio.to_thread(
                score_cache.read_top, req.market, n=req.max_results, max_age_seconds=999999999
            )
            if cached_fallback:
                regime_id = _get_live_regime_id(req.market)
                ai_scores = _cache_rows_to_ai_scores(cached_fallback[:req.max_results], req.market, regime_id)
                ai_scores = _apply_preset_filters(ai_scores, req)
                return ScreenerResponse(
                    regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
                    regime_id=regime_id,
                    results=ai_scores,
                    total=len(ai_scores),
                )
        except Exception:
            pass
        return ScreenerResponse(regime_label="Unknown", regime_id=1, results=[], total=0)


def _run_screener_sync(req: ScreenerRequest, engine: Any) -> ScreenerResponse:
    """Blocking screener compute — runs in thread pool."""
    tickers = req.tickers or UNIVERSE_BY_MARKET.get(req.market, UNIVERSE_BY_MARKET["US"])
    snapshot = build_real_snapshot(tickers, req.market)
    result_df = engine.compute(snapshot)

    filtered = result_df[result_df["composite_score"] >= req.min_score]
    filtered = filtered.sort_values("composite_score", ascending=False)

    # QuantFactor Engine filters
    if req.min_anjali_composite is not None or req.valuation_sweet_spot or req.loss_making is not None:
        from nq_api.score_builder import get_anjali_enrichment
        anjali_pass = []
        for _, row in filtered.iterrows():
            a = get_anjali_enrichment(str(row["ticker"]), req.market)
            if a is None:
                continue  # No QuantFactor data — skip if filters active
            comp = a.get("composite_anjali_score")
            if req.min_anjali_composite is not None and (comp is None or comp < req.min_anjali_composite):
                continue
            if req.valuation_sweet_spot:
                # Q2 sweet spot = valuation_score between +0.5 and +1.5
                val_score = a.get("valuation_score")
                if val_score is None or val_score < 0.5 or val_score > 1.5:
                    continue
            if req.loss_making is False:
                # Exclude loss-making companies
                if a.get("loss_profit_yoy") or a.get("loss_profit_ttm") or a.get("loss_profit_qoq"):
                    continue
            anjali_pass.append(row)
        if anjali_pass:
            filtered = pd.DataFrame(anjali_pass)

    ranked_scores = rank_scores_in_universe(filtered).reset_index(drop=True)
    filtered = filtered.reset_index(drop=True).head(req.max_results)

    regime_id = int(result_df["regime_id"].iloc[0]) if not result_df.empty else 1
    ai_scores = [
        row_to_ai_score(row, req.market, score_1_10_override=int(ranked_scores.iloc[i]))
        for i, (_, row) in enumerate(filtered.iterrows())
    ]
    ai_scores = _apply_preset_filters(ai_scores, req)

    return ScreenerResponse(
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        regime_id=regime_id,
        results=ai_scores,
        total=len(ai_scores),
    )
