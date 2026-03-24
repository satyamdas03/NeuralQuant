# apps/api/src/nq_api/routes/stocks.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal
import numpy as np
import pandas as pd
from dataclasses import dataclass

from nq_api.deps import get_signal_engine
from nq_api.schemas import AIScore
from nq_api.score_builder import row_to_ai_score
from nq_signals.engine import SignalEngine, UniverseSnapshot

router = APIRouter()


@dataclass
class _SyntheticMacro:
    """Phase 2 synthetic macro stub. Phase 3: replace with FREDConnector snapshot."""
    vix: float = 18.0
    spx_vs_200ma: float = 0.02
    hy_spread_oas: float = 350.0
    ism_pmi: float = 51.0
    yield_spread_2y10y: float = 0.10
    spx_return_1m: float = 0.01


def _build_snapshot(ticker: str, market: str) -> UniverseSnapshot:
    """Build snapshot within the full reference universe so percentile ranks match
    the screener — a single-stock universe always ranks at 100th percentile of itself.
    Phase 3 will replace synthetic data with real-time DataStore lookups.
    """
    from nq_api.universe import UNIVERSE_BY_MARKET

    universe = list(UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"]))
    if ticker not in universe:
        universe = [ticker] + universe[:19]

    seeds = [hash(t) % (2**31 - 1) for t in universe]
    fundamentals = pd.DataFrame([{
        "ticker": t,
        "gross_profit_margin": np.random.RandomState(s).uniform(0.1, 0.9),
        "accruals_ratio":      np.random.RandomState(s + 1).uniform(-0.15, 0.15),
        "piotroski":           int(np.random.RandomState(s + 2).randint(2, 9)),
        "momentum_raw":        np.random.RandomState(s + 3).uniform(-0.3, 0.6),
        "short_interest_pct":  np.random.RandomState(s + 4).uniform(0.005, 0.20),
    } for t, s in zip(universe, seeds)])

    return UniverseSnapshot(
        tickers=universe,
        market=market,
        fundamentals=fundamentals,
        macro=_SyntheticMacro(),
    )


@router.get("/{ticker}", response_model=AIScore)
def get_stock_score(
    ticker: str,
    market: Literal["US", "IN", "GLOBAL"] = Query("US"),
    engine: SignalEngine = Depends(get_signal_engine),
) -> AIScore:
    ticker_upper = ticker.upper()
    snapshot = _build_snapshot(ticker_upper, market)
    result_df = engine.compute(snapshot)

    matching = result_df[result_df["ticker"] == ticker_upper]
    if matching.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    return row_to_ai_score(matching.iloc[0], market)
