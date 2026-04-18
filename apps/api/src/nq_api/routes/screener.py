# apps/api/src/nq_api/routes/screener.py
from fastapi import APIRouter, Depends

from nq_api.deps import get_signal_engine
from nq_api.schemas import ScreenerRequest, ScreenerResponse
from nq_api.score_builder import row_to_ai_score, rank_scores_in_universe, REGIME_LABELS
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot
from nq_signals.engine import SignalEngine
from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User

router = APIRouter()


@router.post("", response_model=ScreenerResponse)
def run_screener(
    req: ScreenerRequest,
    engine: SignalEngine = Depends(get_signal_engine),
    user: User = Depends(enforce_tier_quota("screener")),
) -> ScreenerResponse:
    tickers = req.tickers or UNIVERSE_BY_MARKET.get(req.market, UNIVERSE_BY_MARKET["US"])
    snapshot = build_real_snapshot(tickers, req.market)
    result_df = engine.compute(snapshot)

    filtered = result_df[result_df["composite_score"] >= req.min_score]
    filtered = filtered.sort_values("composite_score", ascending=False)
    # Rank within FULL result set (before head) so top-20 still gets a spread 1-10 score
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
