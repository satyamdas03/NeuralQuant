# apps/api/src/nq_api/routes/screener.py
from fastapi import APIRouter, Depends
import pandas as pd
import numpy as np

from nq_api.deps import get_signal_engine
from nq_api.schemas import ScreenerRequest, ScreenerResponse
from nq_api.score_builder import row_to_ai_score, REGIME_LABELS
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.routes.stocks import _SyntheticMacro   # reuse the Phase 2 macro stub
from nq_signals.engine import SignalEngine, UniverseSnapshot

router = APIRouter()


def _build_universe_snapshot(tickers: list[str], market: str) -> UniverseSnapshot:
    """Synthetic fundamentals for Phase 2. Phase 3: real DataStore lookup."""
    seeds = [hash(t) % (2**31 - 1) for t in tickers]
    fundamentals = pd.DataFrame([{
        "ticker": t,
        "gross_profit_margin": (np.random.RandomState(s).uniform(0.1, 0.9)),
        "accruals_ratio":      (np.random.RandomState(s + 1).uniform(-0.15, 0.15)),
        "piotroski":           int(np.random.RandomState(s + 2).randint(2, 9)),
        "momentum_raw":        (np.random.RandomState(s + 3).uniform(-0.3, 0.6)),
        "short_interest_pct":  (np.random.RandomState(s + 4).uniform(0.005, 0.20)),
    } for t, s in zip(tickers, seeds)])

    return UniverseSnapshot(
        tickers=tickers,
        market=market,
        fundamentals=fundamentals,
        macro=_SyntheticMacro(),
    )


@router.post("", response_model=ScreenerResponse)
def run_screener(
    req: ScreenerRequest,
    engine: SignalEngine = Depends(get_signal_engine),
) -> ScreenerResponse:
    tickers = req.tickers or UNIVERSE_BY_MARKET.get(req.market, UNIVERSE_BY_MARKET["US"])
    snapshot = _build_universe_snapshot(tickers, req.market)
    result_df = engine.compute(snapshot)

    # Apply min_score filter, sort descending, take top N
    filtered = result_df[result_df["composite_score"] >= req.min_score]
    filtered = filtered.sort_values("composite_score", ascending=False)
    filtered = filtered.head(req.max_results)

    regime_id = int(result_df["regime_id"].iloc[0]) if not result_df.empty else 1
    ai_scores = [row_to_ai_score(row, req.market) for _, row in filtered.iterrows()]

    return ScreenerResponse(
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        regime_id=regime_id,
        results=ai_scores,
        total=len(ai_scores),
    )
