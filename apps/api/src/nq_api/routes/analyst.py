"""POST /analyst — runs PARA-DEBATE and returns full analyst report."""
import asyncio
from fastapi import APIRouter, Depends
from nq_api.schemas import AnalystRequest, AnalystResponse
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.deps import get_signal_engine
from nq_api.routes.stocks import _build_snapshot

router = APIRouter()


@router.post("", response_model=AnalystResponse)
async def run_analyst(req: AnalystRequest) -> AnalystResponse:
    engine = get_signal_engine()
    snapshot = _build_snapshot(req.ticker.upper(), req.market)
    result_df = engine.compute(snapshot)

    # Build context from synthetic macro stubs + engine output
    context = {
        "market": req.market,
        "vix": 18.0,
        "ism_pmi": 51.0,
        "regime_label": "Risk-On",
        "hy_spread_oas": 350.0,
        "spx_return_1m": 0.01,
        "spx_vs_200ma": 0.02,
        "yield_spread_2y10y": 0.10,
    }

    if not result_df.empty:
        row = result_df.iloc[0]
        context.update({
            "composite_score": float(row.get("composite_score", 0.5)),
            "quality_percentile": float(row.get("quality_percentile", 0.5)),
            "momentum_percentile": float(row.get("momentum_percentile", 0.5)),
            "short_interest_percentile": float(row.get("short_interest_percentile", 0.5)),
            "momentum_raw": float(row.get("momentum_raw", 0.0)),
        })

    orch = ParaDebateOrchestrator()
    return await orch.analyse(ticker=req.ticker.upper(), market=req.market, context=context)
