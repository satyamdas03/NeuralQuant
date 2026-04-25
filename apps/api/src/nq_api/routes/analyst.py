"""POST /analyst — runs PARA-DEBATE and returns full analyst report.

/analyst        — standard JSON response (for backward compat; legacy path)
/analyst/stream — Server-Sent Events streaming response (preferred)
                  Sends keep-alive pings every 10s so Render never drops the
                  idle connection during the 60–120 s multi-agent debate.
"""
import asyncio
import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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


@router.post("/stream")
async def run_analyst_stream(
    req: AnalystRequest,
    user: User = Depends(enforce_tier_quota("analyst")),
) -> StreamingResponse:
    """SSE variant of /analyst.

    Sends keep-alive pings every 8 s from the very first byte — including
    while context is being built — so Render's 30 s idle-connection timeout
    never fires.  The frontend reads the stream and renders the result when
    status=done.

    SSE event format:
      data: {"status":"running"}   — keep-alive tick (ignored by UI)
      data: {"status":"done","result":{...AnalystResponse...}}
      data: {"status":"error","message":"..."}
      data: [DONE]                 — stream closed
    """
    engine = get_signal_engine()
    ticker = req.ticker.upper()
    market = req.market

    async def generate():
        # ── Phase 1: build context while streaming keep-alive pings ──
        # This prevents Render's proxy from dropping the connection during
        # the 10-30 s context-building phase (yfinance calls for 20+ tickers).
        context: dict | None = None
        context_error: str | None = None

        async def _build():
            nonlocal context, context_error
            try:
                ctx = await asyncio.to_thread(_build_context_from_cache, ticker, market)
                if ctx is None:
                    ctx = await asyncio.to_thread(_build_analyst_context, ticker, market, engine)
                context = ctx
            except Exception as exc:
                log.exception("PARA-DEBATE context build failed for %s", ticker)
                context_error = str(exc)

        build_task = asyncio.create_task(_build())

        while not build_task.done():
            yield 'data: {"status":"running"}\n\n'
            try:
                await asyncio.wait_for(asyncio.shield(build_task), timeout=8.0)
            except asyncio.TimeoutError:
                pass

        if context_error:
            yield f'data: {json.dumps({"status": "error", "message": context_error})}\n\n'
            yield "data: [DONE]\n\n"
            return

        if context is None:
            yield f'data: {json.dumps({"status": "error", "message": "Failed to build context"})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # ── Phase 2: run 7-agent debate while streaming keep-alive pings ──
        result_holder: dict = {}
        done_event = asyncio.Event()

        async def _run_debate() -> None:
            try:
                orch = ParaDebateOrchestrator()
                result_holder["result"] = await orch.analyse(
                    ticker=ticker, market=market, context=context
                )
            except Exception as exc:
                log.exception("PARA-DEBATE stream failed for %s", ticker)
                result_holder["error"] = str(exc)
            finally:
                done_event.set()

        asyncio.create_task(_run_debate())

        while not done_event.is_set():
            yield 'data: {"status":"running"}\n\n'
            try:
                await asyncio.wait_for(asyncio.shield(done_event.wait()), timeout=8.0)
            except asyncio.TimeoutError:
                pass

        if "error" in result_holder:
            yield f'data: {json.dumps({"status": "error", "message": result_holder["error"]})}\n\n'
        else:
            resp: AnalystResponse = result_holder["result"]
            yield f'data: {json.dumps({"status": "done", "result": resp.model_dump()})}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
