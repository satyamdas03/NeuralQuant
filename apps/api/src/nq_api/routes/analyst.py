"""POST /analyst — runs PARA-DEBATE and returns full analyst report."""
import asyncio
from fastapi import APIRouter, Depends
from nq_api.schemas import AnalystRequest, AnalystResponse
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.deps import get_signal_engine
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot, fetch_real_macro
from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User

router = APIRouter()


@router.post("", response_model=AnalystResponse)
async def run_analyst(
    req: AnalystRequest,
    user: User = Depends(enforce_tier_quota("analyst")),
) -> AnalystResponse:
    engine = get_signal_engine()
    ticker = req.ticker.upper()

    # Compute within reference universe for meaningful percentile ranks
    universe = list(UNIVERSE_BY_MARKET.get(req.market, UNIVERSE_BY_MARKET["US"]))
    if ticker not in universe:
        universe = [ticker] + universe[:19]

    snapshot = build_real_snapshot(universe, req.market)
    result_df = engine.compute(snapshot)
    macro = fetch_real_macro()

    # Build context from real macro + engine output
    regime_id = int(result_df["regime_id"].iloc[0]) if not result_df.empty else 1
    regime_labels = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}

    context = {
        "market": req.market,
        # Market regime
        "regime_label": regime_labels.get(regime_id, "Risk-On"),
        # yfinance macro
        "vix": round(macro.vix, 2),
        "spx_return_1m": round(macro.spx_return_1m * 100, 2),   # as %
        "spx_vs_200ma": round(macro.spx_vs_200ma * 100, 2),     # as %
        # FRED macro
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
            # Raw fundamentals for richer analyst context
            "gross_profit_margin":       round(float(row.get("gross_profit_margin", 0.0)), 3),
            "piotroski":                 int(row.get("piotroski", 5)),
            "pe_ttm":                    round(float(row.get("pe_ttm", 20.0)), 1),
            "pb_ratio":                  round(float(row.get("pb_ratio", 2.0)), 2),
            "beta":                      round(float(row.get("beta", 1.0)), 2),
            "realized_vol_1y":           round(float(row.get("realized_vol_1y", 0.20)), 3),
        })

    orch = ParaDebateOrchestrator()
    return await orch.analyse(ticker=ticker, market=req.market, context=context)
