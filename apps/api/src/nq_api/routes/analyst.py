"""POST /analyst — runs PARA-DEBATE and returns full analyst report."""
import asyncio
import logging
from fastapi import APIRouter, Depends
from nq_api.schemas import AnalystRequest, AnalystResponse
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.deps import get_signal_engine
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot, fetch_real_macro
from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User
from nq_api.cache import score_cache

log = logging.getLogger(__name__)
router = APIRouter()


def _build_analyst_context(ticker: str, market: str, engine) -> dict:
    """Synchronous context builder — runs in a thread pool."""
    universe = list(UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"]))
    if ticker not in universe:
        universe = [ticker] + universe[:19]

    snapshot = build_real_snapshot(universe, market)
    result_df = engine.compute(snapshot)
    macro = fetch_real_macro()

    regime_id = int(result_df["regime_id"].iloc[0]) if not result_df.empty else 1
    regime_labels = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}

    context = {
        "market": market,
        "regime_label": regime_labels.get(regime_id, "Risk-On"),
        "vix": round(macro.vix, 2),
        "spx_return_1m": round(macro.spx_return_1m * 100, 2),
        "spx_vs_200ma": round(macro.spx_vs_200ma * 100, 2),
        "hy_spread_oas": round(macro.hy_spread_oas, 1),
        "ism_pmi": round(macro.ism_pmi, 1),
        "yield_spread_2y10y": round(macro.yield_spread_2y10y, 3),
        "yield_10y": round(macro.yield_10y, 2),
        "yield_2y": round(macro.yield_2y, 2),
        "cpi_yoy": round(macro.cpi_yoy, 2),
        "fed_funds_rate": round(macro.fed_funds_rate, 2),
        "fred_sourced": macro.fred_sourced,
    }

    matching = result_df[result_df["ticker"] == ticker]
    if not matching.empty:
        row = matching.iloc[0]
        context.update({
            "composite_score":           round(float(row.get("composite_score", 0.5)), 4),
            "quality_percentile":        round(float(row.get("quality_percentile", 0.5)), 3),
            "momentum_percentile":       round(float(row.get("momentum_percentile", 0.5)), 3),
            "value_percentile":          round(float(row.get("value_percentile", 0.5)), 3),
            "low_vol_percentile":        round(float(row.get("low_vol_percentile", 0.5)), 3),
            "short_interest_percentile": round(float(row.get("short_interest_percentile", 0.5)), 3),
            "momentum_raw":              round(float(row.get("momentum_raw", 0.0)), 4),
            "gross_profit_margin":       round(float(row.get("gross_profit_margin", 0.0)), 3),
            "piotroski":                 int(row.get("piotroski", 5)),
            "pe_ttm":                    round(float(row.get("pe_ttm", 20.0)), 1),
            "pb_ratio":                  round(float(row.get("pb_ratio", 2.0)), 2),
            "beta":                      round(float(row.get("beta", 1.0)), 2),
            "realized_vol_1y":           round(float(row.get("realized_vol_1y", 0.20)), 3),
        })

    return context


def _build_context_from_cache(ticker: str, market: str) -> dict | None:
    """Fast path: build analyst context from Supabase score_cache (sub-100ms)."""
    try:
        cached = score_cache.read_one(ticker, market, max_age_seconds=172800)
    except Exception:
        return None
    if not cached:
        return None

    try:
        from nq_api.data_builder import fetch_real_macro
        macro = fetch_real_macro()
        regime_id = cached.get("regime_id", 1)
        regime_labels = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}

        context = {
            "market": market,
            "regime_label": regime_labels.get(regime_id, "Risk-On"),
            "vix": round(macro.vix, 2),
            "spx_return_1m": round(macro.spx_return_1m * 100, 2),
            "spx_vs_200ma": round(macro.spx_vs_200ma * 100, 2),
            "hy_spread_oas": round(macro.hy_spread_oas, 1),
            "ism_pmi": round(macro.ism_pmi, 1),
            "yield_spread_2y10y": round(macro.yield_spread_2y10y, 3),
            "yield_10y": round(macro.yield_10y, 2),
            "yield_2y": round(macro.yield_2y, 2),
            "cpi_yoy": round(macro.cpi_yoy, 2),
            "fed_funds_rate": round(macro.fed_funds_rate, 2),
            "fred_sourced": macro.fred_sourced,
            "composite_score":           round(float(cached.get("composite_score", 0.5)), 4),
            "quality_percentile":        round(float(cached.get("quality_percentile", 0.5)), 3),
            "momentum_percentile":       round(float(cached.get("momentum_percentile", 0.5)), 3),
            "value_percentile":          round(float(cached.get("value_percentile", 0.5)), 3),
            "low_vol_percentile":        round(float(cached.get("low_vol_percentile", 0.5)), 3),
            "short_interest_percentile": round(float(cached.get("short_interest_percentile", 0.5)), 3),
            "momentum_raw":              round(float(cached.get("momentum_raw", 0.0)), 4),
            "gross_profit_margin":       round(float(cached.get("gross_profit_margin", 0.0)), 3),
            "piotroski":                 int(cached.get("piotroski", 5)),
            "pe_ttm":                    round(float(cached.get("pe_ttm", 20.0)), 1),
            "pb_ratio":                  round(float(cached.get("pb_ratio", 2.0)), 2),
            "beta":                      round(float(cached.get("beta", 1.0)), 2),
            "realized_vol_1y":           round(float(cached.get("realized_vol_1y", 0.20)), 3),
        }
        return context
    except Exception as e:
        log.warning("cache context build failed for %s: %s", ticker, e)
        return None


@router.post("", response_model=AnalystResponse)
async def run_analyst(
    req: AnalystRequest,
    user: User = Depends(enforce_tier_quota("analyst")),
) -> AnalystResponse:
    engine = get_signal_engine()
    ticker = req.ticker.upper()

    # Cache-first: try building context from score_cache (fast, avoids blocking event loop)
    context = await asyncio.to_thread(_build_context_from_cache, ticker, req.market)

    if context is None:
        # Slow path: offload blocking I/O to thread pool so event loop stays free
        context = await asyncio.to_thread(_build_analyst_context, ticker, req.market, engine)

    orch = ParaDebateOrchestrator()
    return await orch.analyse(ticker=ticker, market=req.market, context=context)
