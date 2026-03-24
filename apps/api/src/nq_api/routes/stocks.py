# apps/api/src/nq_api/routes/stocks.py
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from nq_api.deps import get_signal_engine
from nq_api.schemas import AIScore
from nq_api.score_builder import row_to_ai_score
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot
from nq_signals.engine import SignalEngine

router = APIRouter()


@router.get("/{ticker}", response_model=AIScore)
def get_stock_score(
    ticker: str,
    market: Literal["US", "IN", "GLOBAL"] = Query("US"),
    engine: SignalEngine = Depends(get_signal_engine),
) -> AIScore:
    ticker_upper = ticker.upper()

    # Compute within the full reference universe so percentile ranks are meaningful
    # (same pool as the screener — single-stock universe always ranks at 100th percentile)
    universe = list(UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"]))
    if ticker_upper not in universe:
        universe = [ticker_upper] + universe[:19]

    snapshot = build_real_snapshot(universe, market)
    result_df = engine.compute(snapshot)

    matching = result_df[result_df["ticker"] == ticker_upper]
    if matching.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    return row_to_ai_score(matching.iloc[0], market)
