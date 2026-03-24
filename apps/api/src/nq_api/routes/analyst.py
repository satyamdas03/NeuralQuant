"""POST /analyst — runs PARA-DEBATE and returns full analyst report."""
import asyncio
from fastapi import APIRouter, Depends
from nq_api.schemas import AnalystRequest, AnalystResponse
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.deps import get_signal_engine
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot, fetch_real_macro

router = APIRouter()


@router.post("", response_model=AnalystResponse)
async def run_analyst(req: AnalystRequest) -> AnalystResponse:
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
    context = {
        "market": req.market,
        "vix": macro.vix,
        "ism_pmi": macro.ism_pmi,
        "regime_label": "Risk-On",
        "hy_spread_oas": macro.hy_spread_oas,
        "spx_return_1m": macro.spx_return_1m,
        "spx_vs_200ma": macro.spx_vs_200ma,
        "yield_spread_2y10y": macro.yield_spread_2y10y,
    }

    matching = result_df[result_df["ticker"] == ticker]
    if not matching.empty:
        row = matching.iloc[0]
        context.update({
            "composite_score": float(row.get("composite_score", 0.5)),
            "quality_percentile": float(row.get("quality_percentile", 0.5)),
            "momentum_percentile": float(row.get("momentum_percentile", 0.5)),
            "short_interest_percentile": float(row.get("short_interest_percentile", 0.5)),
            "momentum_raw": float(row.get("momentum_raw", 0.0)),
        })

    orch = ParaDebateOrchestrator()
    return await orch.analyse(ticker=ticker, market=req.market, context=context)
