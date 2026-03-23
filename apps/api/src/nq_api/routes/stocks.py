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
    """Build a minimal UniverseSnapshot for a single ticker with synthetic data.
    Phase 3 will replace this with real-time data from DataStore.
    """
    np.random.seed(hash(ticker) % (2**31))

    fundamentals = pd.DataFrame([{
        "ticker": ticker,
        "gross_profit_margin": np.random.uniform(0.2, 0.8),
        "accruals_ratio": np.random.uniform(-0.1, 0.1),
        "piotroski": int(np.random.randint(3, 9)),
        "momentum_raw": np.random.uniform(-0.2, 0.5),
        "short_interest_pct": np.random.uniform(0.01, 0.15),
    }])

    return UniverseSnapshot(
        tickers=[ticker],
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
    snapshot = _build_snapshot(ticker.upper(), market)
    result_df = engine.compute(snapshot)

    if result_df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    row = result_df.iloc[0]
    return row_to_ai_score(row, market)
