"""POST /query — natural language financial query endpoint."""
import asyncio
import json as _json
import os
import re
import time
from datetime import date

import anthropic
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import logging

from nq_api.schemas import QueryRequest, QueryResponse, StructuredQueryResponse, ReasoningBlock, MetricItem, ScenarioItem, ComparisonItem, StockSummary, UserProfile, ClarificationQuestion, ConversationMessage

log = logging.getLogger(__name__)
from nq_api.auth.rate_limit import enforce_tier_quota
from nq_api.auth.models import User
from nq_api.auth.deps import get_current_user_optional
import nq_api.dart_router as dart
logger = logging.getLogger(__name__)

router = APIRouter()

# ── Service module imports ────────────────────────────────────────────────────
from nq_api.services.constants import (
    MODEL, _CLOUD_MODEL, _STOP_WORDS, _SECTOR_MAP, _PORTFOLIO_KEYWORDS,
    _CLARIFICATION_STOCK_KEYWORDS, _SECTOR_KEYWORDS, _CLARIFICATION_SKIP_PATTERNS,
    _NSE_NAME_MAP, _TICKER_STOP_WORDS, _SCREENER_KEYWORDS, _INDIA_KEYWORDS,
    _PHASE_LABELS,
)
from nq_api.services.prompts import (
    _SYSTEM, _SYSTEM_STRUCTURED, _PORTFOLIO_OUTPUT_RULES,
    _PROFILE_PROMPT_TEMPLATE, _STRUCTURED_TOOL,
    MORGAN_PERSONA, MORGAN_STYLE_RULES, MORGAN_RESEARCH_REPORT_PROMPT,
    MORGAN_SECTOR_PROMPT,
)
from nq_api.services.anthropic_helpers import (
    _is_ollama_proxy, _query_client, _call_anthropic_with_retry,
)
from nq_api.services.conversation import (
    _save_conversation_turn, _load_conversation_history,
)
from nq_api.services.portfolio import (
    _is_portfolio_intent, _build_profile_prompt,
    _infer_portfolio_market, _validate_and_fill_portfolio_prices,
)
from nq_api.services.stock_summary import _build_stock_summary
from nq_api.services.parsing import (
    _detect_tickers_in_question, _fmt_price_row, _parse_query_response,
    _extract_json_from_llm, _extract_tool_use_input, _structured_from_markdown,
)
from nq_api.services.clarification import (
    _needs_clarification, _fetch_fmp_context_for_clarification,
    _generate_clarification_questions,
)
from nq_api.services.enrichment import (
    _fetch_relevant_news, _fetch_finnhub_news_summaries, _fetch_enrichment,
    _fetch_india_macro, _build_macro_context, _build_market_snapshot,
    _fetch_dynamic_nse_stock, _enrich_with_platform_data, _enrich_snap_structured,
)

# ── Post-processing: validate LLM output against injected data ────────────────
from nq_api.validation import (
    extract_verified_values,
    validate_metrics,
    validate_summary_prices,
    validate_response,
    validate_portfolio_stocks,
)


@router.post("", response_model=QueryResponse)
async def run_nl_query(
    req: QueryRequest,
    user: User | None = Depends(get_current_user_optional),
) -> QueryResponse:
    if not req.question or len(req.question.strip()) < 3:
        return QueryResponse(
            answer="Please enter a question (at least 3 characters).",
            data_sources=[],
            follow_up_questions=["What is the current Nifty level?", "Which Indian stocks rank highest?", "What is the Fed funds rate?"],
            route="REACT",
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return QueryResponse(
            answer="Query service unavailable: ANTHROPIC_API_KEY not configured.",
            data_sources=[],
            follow_up_questions=[],
            route="REACT",
        )

    # ── DART routing ──────────────────────────────────────────────────────────
    route, _is_report = dart.classify_query(req.question, req.ticker)

    if route == "SNAP":
        return await dart.handle_snap(req)

    if route == "DEEP":
        return await dart.handle_deep(req)

    # REACT: existing LLM-powered logic with optimized context
    client, query_model = _query_client(api_key)

    # ── Detect ticker from question when not provided ───────────────────────
    effective_ticker = req.ticker
    if not effective_ticker:
        try:
            detected, _ = _detect_tickers_in_question(req.question, req.market or "US")
            if detected:
                effective_ticker = detected[0].replace(".NS", "").replace(".BO", "")
        except Exception:
            pass

    # ── Offload blocking I/O to thread pool ──────────────────────────────────
    # Each task gets a hard cap so the total context-build phase completes in
    # ≤ 25 s — leaving ample headroom for the 300 s Anthropic timeout.
    # Note: wait_for cancels the asyncio task on timeout but the underlying
    # thread may still run; this is a resource trade-off vs correct behaviour.
    today = date.today().strftime("%B %d, %Y")

    async def _timed(coro, timeout: float, default):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            return default

    enrichment, headlines, macro_ctx, platform_ctx, finnhub_news = await asyncio.gather(
        _timed(asyncio.to_thread(_fetch_enrichment, effective_ticker, req.market or 'US'), 15.0, {}),
        _timed(asyncio.to_thread(_fetch_relevant_news, req.question, req.ticker, 5), 8.0, []),
        _timed(asyncio.to_thread(_build_macro_context, req.question, req.market or "US", today), 10.0, None),
        _timed(asyncio.to_thread(_enrich_with_platform_data, req.question, req.market or "US"), 15.0, None),
        _timed(asyncio.to_thread(_fetch_finnhub_news_summaries, req.ticker, req.market or "US", 5), 8.0, []),
    )

    context_parts = [
        f"Today's date: {today}",
        f"User question: {req.question}",
    ]
    if macro_ctx:
        context_parts.append(macro_ctx)
    if platform_ctx:
        context_parts.append(platform_ctx)
    if req.ticker:
        context_parts.append(f"Stock in focus: {req.ticker} ({req.market or 'US'} market)")
        # Sector peer comparison
        try:
            from nq_api.universe import sector_of
            from nq_api.cache.score_cache import read_sector_median
            sector = sector_of(req.ticker, req.market or "US")
            if sector and sector != "Unknown":
                medians = read_sector_median(sector, req.market or "US")
                if medians:
                    lines = [f"Sector median ({sector}):"]
                    for k, v in medians.items():
                        if v is not None:
                            lines.append(f"  {k}: {round(v, 3)}")
                    context_parts.append("\n".join(lines))
        except Exception:
            pass
    if headlines:
        context_parts.append("Recent market headlines (use these to answer current-events questions):")
        for h in headlines:
            context_parts.append(f"  • {h}")
    if finnhub_news:
        context_parts.append("Detailed news summaries with article excerpts (use these for deeper context — they contain the FULL available text, not just headlines):")
        for a in finnhub_news:
            title_text = a.get("title", "")
            summary_text = a.get("summary", "")
            body_text = a.get("body", "")
            source_text = a.get("source", "")
            parts = [f"[{source_text}] {title_text}"]
            if summary_text:
                parts.append(f"  Summary: {summary_text}")
            if body_text:
                parts.append(f"  Article excerpt: {body_text[:800]}")
            if summary_text or body_text:
                context_parts.append("  • " + "\n  ".join(parts))
    if enrichment:
        tech_lines = ["Technical indicators & sentiment (REAL-TIME DATA):"]
        field_labels = {"rsi_14": "RSI-14", "macd_line": "MACD", "macd_signal": "MACD Signal",
            "macd_hist": "MACD Histogram", "atr_14": "ATR-14", "sma_50": "SMA-50",
            "sma_200": "SMA-200", "price_vs_sma50": "Price vs SMA50",
            "price_vs_sma200": "Price vs SMA200", "volume_ratio": "Volume Ratio",
            "news_sentiment": "News Sentiment", "news_sentiment_score": "Sentiment Score",
            "news_buzz": "News Buzz", "insider_cluster_score": "Insider Score",
            "insider_net_buy_ratio": "Insider Buy Ratio"}
        for k, label in field_labels.items():
            v = enrichment.get(k)
            if v is not None:
                tech_lines.append(f"  {label}: {v}")
        # Analyst & earnings data from FMP (enriched in analyst.py)
        fmp_labels = {
            "analyst_consensus": "Analyst Consensus",
            "analyst_buy_pct": "Analyst Buy %",
            "analyst_target_avg": "Analyst Target Avg",
            "analyst_target_high": "Analyst Target High",
            "analyst_target_low": "Analyst Target Low",
            "analyst_revenue_est": "Revenue Estimate",
            "analyst_eps_est": "EPS Estimate",
            "analyst_count": "Analyst Count",
            "altman_z_score": "Altman Z-Score",
            "piotroski_score": "Piotroski Score",
            "insider_buys": "Insider Buys",
            "insider_sells": "Insider Sells",
            "insider_shares_bought": "Insider Shares Bought",
            "insider_shares_sold": "Insider Shares Sold",
            "dividend_latest": "Latest Dividend",
            "dividend_yield_pct": "Dividend Yield %",
            "next_earnings_date": "Next Earnings Date",
            "next_earnings_eps_est": "Earnings EPS Estimate",
            # OpenBB enrichment
            "iv_percentile": "IV Percentile",
            "put_call_ratio": "Put/Call Ratio",
            "implied_volatility": "Implied Volatility",
            "yield_curve_2y": "2Y Treasury Yield",
            "yield_curve_10y": "10Y Treasury Yield",
            "yield_curve_spread": "Yield Curve Spread",
        }
        for k, label in fmp_labels.items():
            v = enrichment.get(k)
            if v is not None:
                tech_lines.append(f"  {label}: {v}")
        if len(tech_lines) > 1:
            context_parts.append("\n".join(tech_lines))

    user_msg = "\n".join(context_parts)

    try:
        # Build message list — keep up to 4 prior turns; truncate long messages
        messages = []
        for m in (req.history or [])[-4:]:
            content = m.content[:1500] if len(m.content) > 1500 else m.content
            messages.append({"role": m.role, "content": content})
        messages.append({"role": "user", "content": user_msg})

        # ── Morgan REPORT tier for /v1 (unstructured) ──────────────────────
        _v1_system = _SYSTEM
        if _is_report:
            _v1_system += "\n\n" + MORGAN_PERSONA + "\n\n" + MORGAN_STYLE_RULES
            log.info("Morgan REPORT tier activated for /v1: %s", effective_ticker)

        response = await _call_anthropic_with_retry(
            client,
            model=query_model,
            max_tokens=6000 if _is_report else 3000,
            system=_v1_system,
            messages=messages,
        )
        # Extract text from first text-type block (skip thinking blocks)
        raw = ""
        for block in response.content:
            if block.type == "text":
                raw = block.text
                break
        if not raw:
            raw = response.content[0].text if hasattr(response.content[0], "text") else ""

        # Skip second-pass reasoning — the system prompt already requires
        # "why this not that" reasoning. Second LLM call doubles latency.
        answer_text = raw

        return _parse_query_response(answer_text, route="REACT")
    except (anthropic.APITimeoutError, asyncio.TimeoutError):
        return QueryResponse(
            answer="Query timed out — the AI took too long to respond. Try a shorter question.",
            data_sources=[],
            follow_up_questions=[],
            route="REACT",
        )
    except Exception as exc:
        return QueryResponse(
            answer="An error occurred while processing your query. Please try again.",
            data_sources=[],
            follow_up_questions=[],
            route="REACT",
        )


@router.post("/v2", response_model=StructuredQueryResponse)
async def run_nl_query_v2(
    req: QueryRequest,
    user: User | None = Depends(get_current_user_optional),
) -> StructuredQueryResponse:
    """Structured output version of /query. Returns typed JSON with reasoning blocks."""
    from pydantic import ValidationError
    import json

    if not req.question or len(req.question.strip()) < 3:
        return StructuredQueryResponse(
            verdict="HOLD",
            confidence=0,
            timeframe="Medium-term",
            summary="Please enter a question (at least 3 characters).",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            follow_up_questions=["What is the current Nifty level?", "Which Indian stocks rank highest?"],
            route="REACT",
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return StructuredQueryResponse(
            verdict="HOLD",
            confidence=0,
            timeframe="Medium-term",
            summary="Query service unavailable: ANTHROPIC_API_KEY not configured.",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            route="REACT",
        )

    # ── DART routing ── (SNAP disabled — force REACT for full structured detail)
    classified, _is_report_v2 = dart.classify_query(req.question, req.ticker)
    route = "REACT" if classified == "SNAP" else classified

    # REACT or DEEP: use LLM with structured prompt
    client, query_model = _query_client(api_key)

    # ── Detect ticker and market from question when not provided ───────────
    effective_ticker_v2 = req.ticker
    effective_market_v2 = req.market or "US"
    # India keyword detection — runs regardless of ticker presence
    from nq_api.services.constants import _INDIA_KEYWORDS as _ik_v2
    _q_upper_v2 = req.question.upper()
    _has_india_signal_v2 = any(k in _q_upper_v2 for k in _ik_v2)
    if _has_india_signal_v2 and not req.market:
        effective_market_v2 = "IN"
        log.info("Auto-detected IN market from India keywords in /v2")
    if not effective_ticker_v2:
        try:
            detected, _ = _detect_tickers_in_question(req.question, effective_market_v2)
            if detected:
                effective_ticker_v2 = detected[0].replace(".NS", "").replace(".BO", "")
                # Auto-detect IN market when all detected tickers are Indian
                from nq_api.universe import IN_DEFAULT
                in_set = set(IN_DEFAULT)
                if all(t in in_set for t in detected):
                    effective_market_v2 = "IN"
                    log.info("Auto-detected IN market for /v2: %s", detected)
        except Exception:
            pass

    today = date.today().strftime("%B %d, %Y")

    async def _timed(coro, timeout: float, default):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            return default

    headlines, macro_ctx, platform_ctx, finnhub_news, enrichment = await asyncio.gather(
        _timed(asyncio.to_thread(_fetch_relevant_news, req.question, effective_ticker_v2, 5), 8.0, []),
        _timed(asyncio.to_thread(_build_macro_context, req.question, effective_market_v2, today), 10.0, None),
        _timed(asyncio.to_thread(_enrich_with_platform_data, req.question, effective_market_v2), 15.0, None),
        _timed(asyncio.to_thread(_fetch_finnhub_news_summaries, effective_ticker_v2, effective_market_v2, 5), 8.0, []),
        _timed(asyncio.to_thread(_fetch_enrichment, effective_ticker_v2, effective_market_v2), 15.0, {}),
    )

    context_parts = [
        f"Today's date: {today}",
        f"User question: {req.question}",
    ]
    if macro_ctx:
        context_parts.append(macro_ctx)
    if platform_ctx:
        context_parts.append(platform_ctx)
    if effective_ticker_v2:
        context_parts.append(f"Stock in focus: {effective_ticker_v2} ({effective_market_v2} market)")
        # Sector peer comparison
        try:
            from nq_api.universe import sector_of
            from nq_api.cache.score_cache import read_sector_median
            sector = sector_of(effective_ticker_v2, effective_market_v2)
            if sector and sector != "Unknown":
                medians = read_sector_median(sector, effective_market_v2)
                if medians:
                    lines = [f"Sector median ({sector}):"]
                    for k, v in medians.items():
                        if v is not None:
                            lines.append(f"  {k}: {round(v, 3)}")
                    context_parts.append("\n".join(lines))
        except Exception:
            pass
    if headlines:
        context_parts.append("Recent market headlines (use these to answer current-events questions):")
        for h in headlines:
            context_parts.append(f"  • {h}")
    if finnhub_news:
        context_parts.append("Detailed news summaries with article excerpts (use these for deeper context — they contain the FULL available text, not just headlines):")
        for a in finnhub_news:
            title_text = a.get("title", "")
            summary_text = a.get("summary", "")
            body_text = a.get("body", "")
            source_text = a.get("source", "")
            parts = [f"[{source_text}] {title_text}"]
            if summary_text:
                parts.append(f"  Summary: {summary_text}")
            if body_text:
                parts.append(f"  Article excerpt: {body_text[:800]}")
            if summary_text or body_text:
                context_parts.append("  • " + "\n  ".join(parts))
    if enrichment:
        tech_lines = ["Technical indicators & sentiment (REAL-TIME DATA):"]
        field_labels = {"rsi_14": "RSI-14", "macd_line": "MACD", "macd_signal": "MACD Signal",
            "macd_hist": "MACD Histogram", "atr_14": "ATR-14", "sma_50": "SMA-50",
            "sma_200": "SMA-200", "price_vs_sma50": "Price vs SMA50",
            "price_vs_sma200": "Price vs SMA200", "volume_ratio": "Volume Ratio",
            "news_sentiment": "News Sentiment", "news_sentiment_score": "Sentiment Score",
            "news_buzz": "News Buzz", "insider_cluster_score": "Insider Score",
            "insider_net_buy_ratio": "Insider Buy Ratio"}
        for k, label in field_labels.items():
            v = enrichment.get(k)
            if v is not None:
                tech_lines.append(f"  {label}: {v}")
        # Analyst & earnings data from FMP (enriched in analyst.py)
        fmp_labels = {
            "analyst_consensus": "Analyst Consensus",
            "analyst_buy_pct": "Analyst Buy %",
            "analyst_target_avg": "Analyst Target Avg",
            "analyst_target_high": "Analyst Target High",
            "analyst_target_low": "Analyst Target Low",
            "analyst_revenue_est": "Revenue Estimate",
            "analyst_eps_est": "EPS Estimate",
            "analyst_count": "Analyst Count",
            "altman_z_score": "Altman Z-Score",
            "piotroski_score": "Piotroski Score",
            "insider_buys": "Insider Buys",
            "insider_sells": "Insider Sells",
            "insider_shares_bought": "Insider Shares Bought",
            "insider_shares_sold": "Insider Shares Sold",
            "dividend_latest": "Latest Dividend",
            "dividend_yield_pct": "Dividend Yield %",
            "next_earnings_date": "Next Earnings Date",
            "next_earnings_eps_est": "Earnings EPS Estimate",
            # OpenBB enrichment
            "iv_percentile": "IV Percentile",
            "put_call_ratio": "Put/Call Ratio",
            "implied_volatility": "Implied Volatility",
            "yield_curve_2y": "2Y Treasury Yield",
            "yield_curve_10y": "10Y Treasury Yield",
            "yield_curve_spread": "Yield Curve Spread",
        }
        for k, label in fmp_labels.items():
            v = enrichment.get(k)
            if v is not None:
                tech_lines.append(f"  {label}: {v}")
        if len(tech_lines) > 1:
            context_parts.append("\n".join(tech_lines))

    # QuantFactor Engine context injection
    if effective_ticker_v2:
        try:
            from nq_api.score_builder import get_anjali_enrichment
            from nq_api.agents.anjali_context import build_anjali_context
            anjali_data = get_anjali_enrichment(effective_ticker_v2, effective_market_v2)
            anjali_ctx = build_anjali_context(anjali_data)
            if anjali_ctx:
                context_parts.append(anjali_ctx)
        except Exception as e:
            logger.debug("QuantFactor enrichment lookup failed for %s: %s", effective_ticker_v2, e)

    user_msg = "\n".join(context_parts)

    # Reinforce: if platform_ctx contains CURRENT_PRICE, add an extra reminder at the end
    if platform_ctx and "CURRENT_PRICE" in platform_ctx:
        user_msg += "\n\nREMINDER: ALL values marked [VERIFIED] above are TODAY's live market data (yfinance). You MUST use EXACT P/E, Beta, Price, and Market Cap values shown — your training data has WRONG values for stocks with recent earnings changes or splits (e.g. NVDA P/E is ~42x NOT ~28x, Beta is ~2.2 NOT ~0.9). Wrong financial data causes real investment losses."

    # Load persistent conversation memory if session_key provided
    user_id = str(user.id) if user else None
    persistent_history = []
    if user_id and req.session_key:
        persistent_history = await asyncio.to_thread(
            _load_conversation_history, user_id, req.session_key, limit=10
        )
        if persistent_history:
            context_parts.insert(0, f"[Previous conversation context ({len(persistent_history)} turns)]")
            user_msg = "\n".join(context_parts)

    try:
        messages = []
        # Merge client-provided history, persistent history, and current message
        seen_content = set()
        all_history = list(req.history or [])[-4:]
        for ph in persistent_history:
            all_history.append(ConversationMessage(role=ph["role"], content=ph["content"]))
        for m in all_history[-8:]:  # max 8 total history turns
            content = m.content[:1500] if len(m.content) > 1500 else m.content
            if content not in seen_content:
                seen_content.add(content)
                messages.append({"role": m.role, "content": content})
        messages.append({"role": "user", "content": user_msg})

        # ── Clarification check (ask follow-up before answering) ──────────
        detected_tickers_v2 = []
        if not req.ticker:
            try:
                detected_tickers_v2, _ = _detect_tickers_in_question(req.question, effective_market_v2)
            except Exception:
                pass
        else:
            detected_tickers_v2 = [req.ticker]

        if req.clarification_answers:
            # Inject user's clarification answers into the prompt
            answers_text = "\n".join(f"• {a}" for a in req.clarification_answers)
            user_msg += f"\n\n[USER CONTEXT] User clarified their needs:\n{answers_text}"
            messages[-1] = {"role": "user", "content": user_msg}

        clarification = _needs_clarification(req.question, detected_tickers_v2, route, req.profile)
        # Build dynamic clarification context with live market data
        _fmp_ctx = _fetch_fmp_context_for_clarification(
            detected_tickers_v2[0] if detected_tickers_v2 else "",
            effective_market_v2,
        ) if detected_tickers_v2 else None
        _clarification_qs = _generate_clarification_questions(
            req.question, detected_tickers_v2, effective_market_v2, route,
            fmp_context=_fmp_ctx,
        )
        _ctx_str = "Answer these questions so I can give you a personalized response."
        if _fmp_ctx and detected_tickers_v2:
            _ctx_parts = []
            cur = "₹" if effective_market_v2 == "IN" else "$"
            if _fmp_ctx.get("price"):
                _ctx_parts.append(f"Price: {cur}{_fmp_ctx['price']:,.2f}")
            if _fmp_ctx.get("pe"):
                _ctx_parts.append(f"P/E: {_fmp_ctx['pe']:.1f}x")
            if _fmp_ctx.get("analyst_consensus"):
                _ctx_parts.append(f"Analysts: {_fmp_ctx['analyst_consensus'].title()}")
            if _fmp_ctx.get("dividend_yield"):
                _ctx_parts.append(f"Yield: {_fmp_ctx['dividend_yield']:.1f}%")
            if _fmp_ctx.get("next_earnings_date"):
                _ctx_parts.append(f"Earnings: {_fmp_ctx['next_earnings_date']}")
            if _ctx_parts:
                _ctx_str = f"Live data for {detected_tickers_v2[0]}: {' | '.join(_ctx_parts)}"

        if clarification and not req.clarification_answers:
            return StructuredQueryResponse(
                verdict="HOLD",
                confidence=0,
                timeframe="N/A",
                summary="I'd like to understand your needs better before answering.",
                reasoning=ReasoningBlock(
                    why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                    second_best="N/A", confidence_gap="N/A",
                ),
                clarification_needed=True,
                clarification_questions=_clarification_qs,
                clarification_context=_ctx_str,
                route="REACT",
                data_sources=["NeuralQuant Clarification"],
                follow_up_questions=[],
                metrics=[],
                scenarios=[],
                allocations=[],
                comparisons=[],
            )

        # Portfolio intent detection and prompt injection
        portfolio_intent = _is_portfolio_intent(req.question)

        # If clarification needed, show it before profiler
        # (clarification already returned above if True and no clarification_answers)

        # Check if profile needed for portfolio questions
        # Only show profiler if clarification was NOT needed (or was already answered)
        if portfolio_intent and not req.profile and not clarification:
            return StructuredQueryResponse(
                verdict="HOLD",
                confidence=0,
                timeframe="Medium-term",
                summary="Before I build your portfolio, I need to understand your goals.",
                reasoning=ReasoningBlock(
                    why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                    second_best="N/A", confidence_gap="N/A",
                ),
                profiler_needed=True,
                route="REACT",
                data_sources=["NeuralQuant Profiler"],
                follow_up_questions=[],
                metrics=[],
                scenarios=[],
                allocations=[],
                comparisons=[],
            )

        system_prompt = _SYSTEM_STRUCTURED
        if portfolio_intent:
            system_prompt = _SYSTEM_STRUCTURED + "\n\n" + _PORTFOLIO_OUTPUT_RULES
            snap = _build_market_snapshot(effective_market_v2)
            if snap:
                user_msg = user_msg + "\n\n" + snap
            # Inject profile if present
            if req.profile:
                user_msg = user_msg + "\n\n" + _build_profile_prompt(req.profile)
            messages[-1]["content"] = user_msg

        # ── Morgan REPORT tier injection ──────────────────────────────────────
        if _is_report_v2:
            morgan_extra = "\n\n" + MORGAN_PERSONA + "\n\n" + MORGAN_STYLE_RULES
            # Detect sector query — use sector prompt instead of single-stock report
            _is_sector_q = any(k.lower() in req.question.lower() for k in _SECTOR_KEYWORDS)
            if _is_sector_q and not effective_ticker_v2:
                morgan_extra += "\n\n" + MORGAN_SECTOR_PROMPT
            else:
                # Build report template with available data
                _rpt = MORGAN_RESEARCH_REPORT_PROMPT
                _rpt = _rpt.replace("{COMPANY_NAME}", effective_ticker_v2 or "the company")
                _rpt = _rpt.replace("{TICKER}", effective_ticker_v2 or "N/A")
                # Fill placeholders from verified data extracted from platform context
                _v = extract_verified_values(platform_ctx)
                _rpt = _rpt.replace("{CURRENT_PRICE}", str(_v.get("CURRENT_PRICE", "N/A")))
                _rpt = _rpt.replace("{IRS_PCT}", str(_v.get("IRS_PCT", "N/A")))
                _rpt = _rpt.replace("{G_SCORE}", str(_v.get("G_SCORE", "N/A")))
                _rpt = _rpt.replace("{RISK_EFF_SCORE}", str(_v.get("RISK_EFF_SCORE", "N/A")))
                _rpt = _rpt.replace("{PE_TTM}", str(_v.get("PE_TTM", _v.get("TRAILING_PE", "N/A"))))
                _rpt = _rpt.replace("{FUTURE_PE}", str(_v.get("FUTURE_PE", "N/A")))
                _rpt = _rpt.replace("{SECTOR}", str(_v.get("SECTOR", "N/A")))
                morgan_extra += "\n\n" + _rpt
            system_prompt += morgan_extra
            log.info("Morgan REPORT tier activated for /v2: %s (sector=%s)", effective_ticker_v2, _is_sector_q)

        # Inject profile context for all queries (not just portfolio)
        if req.profile and not portfolio_intent:
            user_msg = user_msg + "\n\n[INVESTOR PROFILE CONTEXT] " + _build_profile_prompt(req.profile)
            messages[-1]["content"] = user_msg

        # Force tool_use for guaranteed structured output (no markdown leakage).
        _report_max_tokens = 12000 if _is_report_v2 else 8000
        response = await _call_anthropic_with_retry(
            client,
            model=query_model,
            max_tokens=_report_max_tokens,
            system=system_prompt,
            tools=[_STRUCTURED_TOOL],
            tool_choice={"type": "tool", "name": _STRUCTURED_TOOL["name"]},
            messages=messages,
        )

        parsed = _extract_tool_use_input(response)
        if parsed:
            try:
                parsed.setdefault("route", route)
                parsed.setdefault("data_sources", [])
                parsed.setdefault("follow_up_questions", [])
                if "reasoning" not in parsed:
                    parsed["reasoning"] = {
                        "why_this": "Based on the highest ForeCast Score and strongest factor alignment",
                        "why_not_alt": "Alternative had lower scores on key factors",
                        "edge_summary": "Selected stock leads on composite score and factor quality",
                        "second_best": "N/A",
                        "confidence_gap": "N/A",
                    }
                # Portfolio validation post-processing
                if portfolio_intent:
                    parsed["is_portfolio_response"] = True
                    if not parsed.get("sebi_disclaimer") or "SEBI" not in parsed.get("sebi_disclaimer", "").upper():
                        parsed["sebi_disclaimer"] = (
                            "This is AI-generated investment research, not SEBI-registered investment advice. "
                            "Please consult a certified financial advisor before investing."
                        )
                    if not parsed.get("portfolio_stocks") and parsed.get("allocations"):
                        parsed["portfolio_stocks"] = []
                        for a in parsed["allocations"]:
                            ticker = a.get("ticker", "")
                            weight = a.get("weight", 0)
                            rationale = a.get("rationale", "")
                            entry_match = re.search(r'Entry[:\s]+([^;\n]+)', rationale)
                            entry_price = entry_match.group(1).strip() if entry_match else None
                            target_match = re.search(r'Target[:\s]+([^;\n]+)', rationale)
                            target_price = target_match.group(1).strip() if target_match else None
                            stop_match = re.search(r'Stop[:\s]+([^;\n]+)', rationale)
                            stop_loss = stop_match.group(1).strip() if stop_match else None
                            parsed["portfolio_stocks"].append({
                                "ticker": ticker,
                                "allocation_pct": weight,
                                "rationale": rationale,
                                "entry_price": entry_price,
                                "target_price": target_price,
                                "stop_loss": stop_loss,
                            })
                    if not parsed.get("scenario_analysis") and parsed.get("scenarios"):
                        parsed["scenario_analysis"] = []
                        scenario_colors = {"Bull": "#22c55e", "Base": "#6366f1", "Bear": "#ef4444"}
                        for s in parsed["scenarios"]:
                            label = s.get("label", "")
                            prob = int(s.get("probability", 0) * 100)
                            parsed["scenario_analysis"].append({
                                "label": label,
                                "probability_pct": prob,
                                "outcome": s.get("target", ""),
                                "description": s.get("thesis", ""),
                                "color": scenario_colors.get(label, "#6366f1"),
                            })
                    if not parsed.get("allocation_breakdown") and parsed.get("allocations"):
                        parsed["allocation_breakdown"] = []
                        for a in parsed["allocations"]:
                            parsed["allocation_breakdown"].append({
                                "label": a.get("ticker", ""),
                                "percentage": a.get("weight", 0),
                                "rationale": a.get("rationale", ""),
                            })
                    if not parsed.get("market_context"):
                        parsed["market_context"] = []
                    if not parsed.get("action_prompts"):
                        parsed["action_prompts"] = []
                    # Validate portfolio stock data against real yfinance
                    if parsed.get("portfolio_stocks"):
                        pf_market = _infer_portfolio_market(parsed["portfolio_stocks"], effective_market_v2)
                        corrected_stocks, corrected_summary, pf_corrections = await asyncio.to_thread(
                            validate_portfolio_stocks, parsed["portfolio_stocks"], pf_market, parsed.get("summary", "")
                        )
                        parsed["portfolio_stocks"] = corrected_stocks
                        if corrected_summary != parsed.get("summary", ""):
                            parsed["summary"] = corrected_summary
                        if pf_corrections and parsed.get("summary"):
                            parsed["summary"] += f" [Data verified: {'; '.join(pf_corrections)}]"
                        # Fill live prices for entry/target/stop_loss
                        pf_market = _infer_portfolio_market(parsed["portfolio_stocks"], effective_market_v2)
                        filled_stocks, fill_notes = await asyncio.to_thread(
                            _validate_and_fill_portfolio_prices, parsed["portfolio_stocks"], pf_market
                        )
                        parsed["portfolio_stocks"] = filled_stocks
                        if fill_notes and parsed.get("summary"):
                            parsed["summary"] += f" [Live prices verified: {'; '.join(fill_notes)}]"
                result = StructuredQueryResponse(**parsed)
                # Validate LLM metrics against injected [VERIFIED] data
                verified = extract_verified_values(platform_ctx)
                _, result.summary, _ = validate_response(result.metrics or [], result.summary or "", verified)
                # Mark as Morgan report if classified
                if _is_report_v2:
                    result.is_report = True
                # Attach stock summary from enrichment data
                result.stock_summary = _build_stock_summary(effective_ticker_v2, effective_market_v2, enrichment, platform_ctx)
                # Persist conversation turn (best-effort)
                if user_id and req.session_key:
                    await asyncio.to_thread(
                        _save_conversation_turn, user_id, req.session_key,
                        "user", req.question, effective_ticker_v2, effective_market_v2
                    )
                    await asyncio.to_thread(
                        _save_conversation_turn, user_id, req.session_key,
                        "assistant", result.summary, effective_ticker_v2, effective_market_v2
                    )
                return result
            except (ValidationError, Exception) as e:
                log.warning("Tool-use structured output validation failed: %s", e)

        # Extreme fallback: tool_use was rejected — salvage from any text block
        raw = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                raw = block.text
                break
        freeform_resp = _parse_query_response(raw, route)
        result = _structured_from_markdown(raw, freeform_resp, route, _build_stock_summary(effective_ticker_v2, effective_market_v2, enrichment, platform_ctx))
        # Validate LLM metrics against injected [VERIFIED] data
        verified = extract_verified_values(platform_ctx)
        _, result.summary, _ = validate_response(result.metrics or [], result.summary or "", verified)
        return result

    except (anthropic.APITimeoutError, asyncio.TimeoutError):
        return StructuredQueryResponse(
            verdict="HOLD", confidence=0, timeframe="Medium-term",
            summary="Query timed out — the AI took too long to respond. Try a shorter question.",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            route=route,
        )
    except Exception as exc:
        return StructuredQueryResponse(
            verdict="HOLD", confidence=0, timeframe="Medium-term",
            summary=f"Query failed: {str(exc)[:200]}",
            reasoning=ReasoningBlock(
                why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                second_best="N/A", confidence_gap="N/A",
            ),
            route=route,
        )


@router.post("/v2/stream")
async def run_nl_query_v2_stream(
    req: QueryRequest,
    user: User | None = Depends(get_current_user_optional),
):
    """SSE streaming variant of /v2. Emits phase labels + keep-alive pings."""
    from pydantic import ValidationError

    async def generate():
        if not req.question or len(req.question.strip()) < 3:
            err = StructuredQueryResponse(
                verdict="HOLD", confidence=0, timeframe="Medium-term",
                summary="Please enter a question (at least 3 characters).",
                reasoning=ReasoningBlock(why_this="N/A",why_not_alt="N/A",edge_summary="N/A",second_best="N/A",confidence_gap="N/A"),
                follow_up_questions=["What is the current Nifty level?"],
                route="REACT",
            )
            yield f'data: {_json.dumps({"status":"done","result":err.model_dump()})}\n\n'
            yield "data: [DONE]\n\n"
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            yield f'data: {_json.dumps({"status":"error","message":"ANTHROPIC_API_KEY not configured"})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # Phase 1: Classify (always REACT — SNAP disabled for richer detail)
        yield f'data: {_json.dumps({"status":"phase","phase":"classify","label":_PHASE_LABELS["classify"]})}\n\n'
        # Force REACT for all queries — user wants every answer detailed with full
        # cards (verdict banner, metrics, reasoning, scenarios, comparisons).
        # SNAP returns short cache-only answers which produce empty/weak cards.
        # DEEP (PARA-DEBATE) is reserved for explicit deep-analysis triggers and
        # is fine to keep. All other queries route to REACT.
        classified, _is_report_stream = dart.classify_query(req.question, req.ticker)
        route = "REACT" if classified == "SNAP" else classified

        # Phase 2-4: Context gathering (parallel)
        client, query_model = _query_client(api_key)
        query_start = time.monotonic()
        today = date.today().strftime("%B %d, %Y")

        # ── Detect ticker and market from question when not provided ───────────
        stream_ticker = req.ticker
        stream_market = req.market or "US"
        # India keyword detection — runs regardless of ticker presence
        from nq_api.services.constants import _INDIA_KEYWORDS
        _q_upper = req.question.upper()
        _has_india_signal = any(k in _q_upper for k in _INDIA_KEYWORDS)
        if _has_india_signal and not req.market:
            stream_market = "IN"
            log.info("Auto-detected IN market from India keywords in /v2/stream")
        if not stream_ticker:
            try:
                detected, _ = _detect_tickers_in_question(req.question, stream_market)
                if detected:
                    stream_ticker = detected[0].replace(".NS", "").replace(".BO", "")
                    # Auto-detect IN market when all detected tickers are Indian
                    from nq_api.universe import IN_DEFAULT
                    in_set = set(IN_DEFAULT)
                    if all(t in in_set for t in detected):
                        stream_market = "IN"
                        log.info("Auto-detected IN market for /v2/stream: %s", detected)
            except Exception:
                pass
        elif req.market:
            stream_market = req.market

        yield f'data: {_json.dumps({"status":"phase","phase":"news","label":_PHASE_LABELS["news"]})}\n\n'
        yield f'data: {_json.dumps({"status":"phase","phase":"macro","label":_PHASE_LABELS["macro"]})}\n\n'
        yield f'data: {_json.dumps({"status":"phase","phase":"platform","label":_PHASE_LABELS["platform"]})}\n\n'

        result_holder: dict = {}
        context_done = asyncio.Event()

        async def _gather_context():
            async def _timed(coro, timeout, default):
                try:
                    return await asyncio.wait_for(coro, timeout=timeout)
                except (asyncio.TimeoutError, Exception):
                    return default

            headlines, macro_ctx, platform_ctx, finnhub_news, enrichment = await asyncio.gather(
                _timed(asyncio.to_thread(_fetch_relevant_news, req.question, stream_ticker, 5), 8.0, []),
                _timed(asyncio.to_thread(_build_macro_context, req.question, stream_market, today), 10.0, None),
                _timed(asyncio.to_thread(_enrich_with_platform_data, req.question, stream_market), 15.0, None),
                _timed(asyncio.to_thread(_fetch_finnhub_news_summaries, stream_ticker, stream_market, 5), 8.0, []),
                _timed(asyncio.to_thread(_fetch_enrichment, stream_ticker, stream_market), 15.0, {}),
            )
            context_parts = [f"Today's date: {today}", f"User question: {req.question}"]
            if macro_ctx:
                context_parts.append(macro_ctx)
            if platform_ctx:
                context_parts.append(platform_ctx)
            if stream_ticker:
                context_parts.append(f"Stock in focus: {stream_ticker} ({stream_market} market)")
                # Sector peer comparison
                try:
                    from nq_api.universe import sector_of
                    from nq_api.cache.score_cache import read_sector_median
                    sector = sector_of(stream_ticker, stream_market)
                    if sector and sector != "Unknown":
                        medians = read_sector_median(sector, stream_market)
                        if medians:
                            lines = [f"Sector median ({sector}):"]
                            for k, v in medians.items():
                                if v is not None:
                                    lines.append(f"  {k}: {round(v, 3)}")
                            context_parts.append("\n".join(lines))
                except Exception:
                    pass
            if headlines:
                context_parts.append("Recent market headlines (use these to answer current-events questions):")
                for h in headlines:
                    context_parts.append(f"  • {h}")
            if finnhub_news:
                context_parts.append("Detailed news summaries (use these for deeper context):")
                for a in finnhub_news:
                    summary_text = a.get("summary", "")
                    title_text = a.get("title", "")
                    source_text = a.get("source", "")
                    if summary_text:
                        context_parts.append(f"  • [{source_text}] {title_text}: {summary_text[:300]}")
            if enrichment:
                tech_lines = ["Technical indicators & sentiment (REAL-TIME DATA):"]
                field_labels = {"rsi_14": "RSI-14", "macd_line": "MACD", "macd_signal": "MACD Signal",
                    "macd_hist": "MACD Histogram", "atr_14": "ATR-14", "sma_50": "SMA-50",
                    "sma_200": "SMA-200", "price_vs_sma50": "Price vs SMA50",
                    "price_vs_sma200": "Price vs SMA200", "volume_ratio": "Volume Ratio",
                    "news_sentiment": "News Sentiment", "news_sentiment_score": "Sentiment Score",
                    "news_buzz": "News Buzz", "insider_cluster_score": "Insider Score",
                    "insider_net_buy_ratio": "Insider Buy Ratio"}
                for k, label in field_labels.items():
                    v = enrichment.get(k)
                    if v is not None:
                        tech_lines.append(f"  {label}: {v}")
                if len(tech_lines) > 1:
                    context_parts.append("\n".join(tech_lines))
            # QuantFactor Engine context injection (streaming endpoint)
            if stream_ticker:
                try:
                    from nq_api.score_builder import get_anjali_enrichment
                    from nq_api.agents.anjali_context import build_anjali_context
                    anjali_data = get_anjali_enrichment(stream_ticker, stream_market)
                    anjali_ctx = build_anjali_context(anjali_data)
                    if anjali_ctx:
                        context_parts.append(anjali_ctx)
                except Exception:
                    pass
            result_holder["user_msg"] = "\n".join(context_parts)
            # Reinforce: if platform_ctx contains CURRENT_PRICE, add reminder
            if platform_ctx and "CURRENT_PRICE" in platform_ctx:
                result_holder["user_msg"] += "\n\nREMINDER: ALL values marked [VERIFIED] above are TODAY's live market data (yfinance). You MUST use EXACT P/E, Beta, Price, and Market Cap values shown — your training data has WRONG values for stocks with recent earnings changes or splits (e.g. NVDA P/E is ~42x NOT ~28x, Beta is ~2.2 NOT ~0.9). Wrong financial data causes real investment losses."
            result_holder["enrichment"] = enrichment
            result_holder["platform_ctx"] = platform_ctx
            context_done.set()

        context_task = asyncio.create_task(_gather_context())
        ctx_start = time.monotonic()
        while not context_done.is_set():
            yield 'data: {"status":"running"}\n\n'
            elapsed = time.monotonic() - ctx_start
            if elapsed > 25:                       # 25s: must be >= max inner timeout (15s) + buffer
                context_task.cancel()
                result_holder.setdefault("error", "Context gathering timed out")
                break
            try:
                await asyncio.wait_for(asyncio.shield(context_done.wait()), timeout=4.0)
            except asyncio.TimeoutError:
                pass

        if "error" in result_holder:
            yield f'data: {_json.dumps({"status":"error","message":result_holder["error"]})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # Context built — emit "context" phase as completed marker
        yield f'data: {_json.dumps({"status":"phase","phase":"context","label":_PHASE_LABELS["context"]})}\n\n'

        # Phase 5+: LLM call broken into prompt → thinking → generate → parse
        yield f'data: {_json.dumps({"status":"phase","phase":"prompt","label":_PHASE_LABELS["prompt"]})}\n\n'
        total_elapsed = time.monotonic() - query_start

        llm_done = asyncio.Event()

        async def _call_llm():
            try:
                # Load persistent conversation memory if session_key provided
                user_id_stream = str(user.id) if user else None
                persistent_history_stream = []
                if user_id_stream and req.session_key:
                    try:
                        persistent_history_stream = await asyncio.to_thread(
                            _load_conversation_history, user_id_stream, req.session_key, limit=10
                        )
                    except Exception:
                        pass

                messages = []
                # Merge client-provided history, persistent history, and current message
                seen_content = set()
                all_history = list(req.history or [])[-4:]
                for ph in persistent_history_stream:
                    all_history.append(ConversationMessage(role=ph["role"], content=ph["content"]))
                for m in all_history[-8:]:
                    content = m.content[:1500] if len(m.content) > 1500 else m.content
                    if content not in seen_content:
                        seen_content.add(content)
                        messages.append({"role": m.role, "content": content})
                messages.append({"role": "user", "content": result_holder["user_msg"]})

                # ── Clarification check (ask follow-up before answering) ──────────
                detected_tickers_stream = []
                if not req.ticker:
                    try:
                        detected_tickers_stream, _ = _detect_tickers_in_question(req.question, stream_market)
                    except Exception:
                        pass
                else:
                    detected_tickers_stream = [req.ticker]

                if req.clarification_answers:
                    answers_text = "\n".join(f"• {a}" for a in req.clarification_answers)
                    result_holder["user_msg"] += f"\n\n[USER CONTEXT] User clarified their needs:\n{answers_text}"
                    messages[-1] = {"role": "user", "content": result_holder["user_msg"]}

                # Build dynamic clarification context with live market data (streaming)
                _fmp_ctx_s = _fetch_fmp_context_for_clarification(
                    detected_tickers_stream[0] if detected_tickers_stream else "",
                    stream_market,
                ) if detected_tickers_stream else None
                _clarification_qs_s = _generate_clarification_questions(
                    req.question, detected_tickers_stream, stream_market, route,
                    fmp_context=_fmp_ctx_s,
                )
                _ctx_str_s = "Answer these questions so I can give you a personalized response."
                if _fmp_ctx_s and detected_tickers_stream:
                    _ctx_parts_s = []
                    cur_s = "₹" if stream_market == "IN" else "$"
                    if _fmp_ctx_s.get("price"):
                        _ctx_parts_s.append(f"Price: {cur_s}{_fmp_ctx_s['price']:,.2f}")
                    if _fmp_ctx_s.get("pe"):
                        _ctx_parts_s.append(f"P/E: {_fmp_ctx_s['pe']:.1f}x")
                    if _fmp_ctx_s.get("analyst_consensus"):
                        _ctx_parts_s.append(f"Analysts: {_fmp_ctx_s['analyst_consensus'].title()}")
                    if _fmp_ctx_s.get("dividend_yield"):
                        _ctx_parts_s.append(f"Yield: {_fmp_ctx_s['dividend_yield']:.1f}%")
                    if _fmp_ctx_s.get("next_earnings_date"):
                        _ctx_parts_s.append(f"Earnings: {_fmp_ctx_s['next_earnings_date']}")
                    if _ctx_parts_s:
                        _ctx_str_s = f"Live data for {detected_tickers_stream[0]}: {' | '.join(_ctx_parts_s)}"

                clarification = _needs_clarification(req.question, detected_tickers_stream, route, req.profile)
                if clarification and not req.clarification_answers:
                    result_holder["result"] = StructuredQueryResponse(
                        verdict="HOLD",
                        confidence=0,
                        timeframe="N/A",
                        summary="I'd like to understand your needs better before answering.",
                        reasoning=ReasoningBlock(
                            why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                            second_best="N/A", confidence_gap="N/A",
                        ),
                        clarification_needed=True,
                        clarification_questions=_clarification_qs_s,
                        clarification_context=_ctx_str_s,
                        route="REACT",
                        data_sources=["NeuralQuant Clarification"],
                        follow_up_questions=[],
                        metrics=[],
                        scenarios=[],
                        allocations=[],
                        comparisons=[],
                    )
                    return

                # Portfolio intent detection and prompt injection
                portfolio_intent = _is_portfolio_intent(req.question)

                # Check if profile needed for portfolio questions
                # Only show profiler if clarification was NOT needed (or was already answered)
                if portfolio_intent and not req.profile and not clarification:
                    result_holder["result"] = StructuredQueryResponse(
                        verdict="HOLD",
                        confidence=0,
                        timeframe="Medium-term",
                        summary="Before I build your portfolio, I need to understand your goals.",
                        reasoning=ReasoningBlock(
                            why_this="N/A", why_not_alt="N/A", edge_summary="N/A",
                            second_best="N/A", confidence_gap="N/A",
                        ),
                        profiler_needed=True,
                        route="REACT",
                        data_sources=["NeuralQuant Profiler"],
                        follow_up_questions=[],
                        metrics=[],
                        scenarios=[],
                        allocations=[],
                        comparisons=[],
                    )
                    return

                system_prompt = _SYSTEM_STRUCTURED
                if portfolio_intent:
                    system_prompt = _SYSTEM_STRUCTURED + "\n\n" + _PORTFOLIO_OUTPUT_RULES
                    snap = _build_market_snapshot(stream_market)
                    if snap:
                        result_holder["user_msg"] = result_holder["user_msg"] + "\n\n" + snap
                    # Inject profile if present
                    if req.profile:
                        result_holder["user_msg"] = result_holder["user_msg"] + "\n\n" + _build_profile_prompt(req.profile)
                    messages[-1]["content"] = result_holder["user_msg"]

                # ── Morgan REPORT tier injection (streaming) ────────────────────
                if _is_report_stream:
                    morgan_extra = "\n\n" + MORGAN_PERSONA + "\n\n" + MORGAN_STYLE_RULES
                    _is_sector_q_s = any(k.lower() in req.question.lower() for k in _SECTOR_KEYWORDS)
                    if _is_sector_q_s and not stream_ticker:
                        morgan_extra += "\n\n" + MORGAN_SECTOR_PROMPT
                    else:
                        _rpt = MORGAN_RESEARCH_REPORT_PROMPT
                        _rpt = _rpt.replace("{COMPANY_NAME}", stream_ticker or "the company")
                        _rpt = _rpt.replace("{TICKER}", stream_ticker or "N/A")
                        # Extract verified values from platform context string
                        _sv = extract_verified_values(result_holder.get("platform_ctx"))
                        _rpt = _rpt.replace("{CURRENT_PRICE}", str(_sv.get("CURRENT_PRICE", "N/A")))
                        _rpt = _rpt.replace("{IRS_PCT}", str(_sv.get("IRS_PCT", "N/A")))
                        _rpt = _rpt.replace("{G_SCORE}", str(_sv.get("G_SCORE", "N/A")))
                        _rpt = _rpt.replace("{RISK_EFF_SCORE}", str(_sv.get("RISK_EFF_SCORE", "N/A")))
                        _rpt = _rpt.replace("{PE_TTM}", str(_sv.get("PE_TTM", _sv.get("TRAILING_PE", "N/A"))))
                        _rpt = _rpt.replace("{FUTURE_PE}", str(_sv.get("FUTURE_PE", "N/A")))
                        _rpt = _rpt.replace("{SECTOR}", str(_sv.get("SECTOR", "N/A")))
                        morgan_extra += "\n\n" + _rpt
                    system_prompt += morgan_extra
                    log.info("Morgan REPORT tier activated for /v2/stream: %s (sector=%s)", stream_ticker, _is_sector_q_s)

                # Inject profile context for all non-portfolio streaming queries
                if req.profile and not portfolio_intent:
                    result_holder["user_msg"] = result_holder["user_msg"] + "\n\n[INVESTOR PROFILE CONTEXT] " + _build_profile_prompt(req.profile)
                    messages[-1]["content"] = result_holder["user_msg"]

                # Force tool_use: model MUST call `respond_with_neuralquant_forecast`
                # with arguments matching the schema. No more markdown leakage.
                # 90s timeout prevents indefinite hangs on complex queries
                _report_max_tokens_stream = 12000 if _is_report_stream else 8000
                try:
                    response = await _call_anthropic_with_retry(
                        client,
                        model=query_model,
                        max_tokens=_report_max_tokens_stream,
                        system=system_prompt,
                        tools=[_STRUCTURED_TOOL],
                        tool_choice={"type": "tool", "name": _STRUCTURED_TOOL["name"]},
                        messages=messages,
                        timeout=90.0,
                    )
                except asyncio.TimeoutError:
                    result_holder["result"] = StructuredQueryResponse(
                        verdict="HOLD", confidence=0, timeframe="Medium-term",
                        summary="Query timed out — the AI took too long to respond. Try a shorter question.",
                        reasoning=ReasoningBlock(why_this="N/A", why_not_alt="N/A", edge_summary="N/A", second_best="N/A", confidence_gap="N/A"),
                        route=route,
                    )
                    llm_done.set()
                    return

                parsed = _extract_tool_use_input(response)
                if parsed:
                    try:
                        parsed.setdefault("route", route)
                        parsed.setdefault("data_sources", [])
                        parsed.setdefault("follow_up_questions", [])
                        if "reasoning" not in parsed:
                            parsed["reasoning"] = {
                                "why_this": "Based on the highest ForeCast Score and strongest factor alignment",
                                "why_not_alt": "Alternative had lower scores on key factors",
                                "edge_summary": "Selected stock leads on composite score and factor quality",
                                "second_best": "N/A",
                                "confidence_gap": "N/A",
                            }
                        # Portfolio validation post-processing (before creating StructuredQueryResponse)
                        log.info("Portfolio intent check: %s, parsed keys: %s", portfolio_intent, list(parsed.keys()))
                        if portfolio_intent:
                            parsed["is_portfolio_response"] = True
                            log.info("Setting is_portfolio_response=True")
                            # Ensure SEBI disclaimer present
                            if not parsed.get("sebi_disclaimer") or "SEBI" not in parsed.get("sebi_disclaimer", "").upper():
                                parsed["sebi_disclaimer"] = (
                                    "This is AI-generated investment research, not SEBI-registered investment advice. "
                                    "Please consult a certified financial advisor before investing."
                                )
                            # Auto-fill portfolio fields from old format if missing
                            if not parsed.get("portfolio_stocks") and parsed.get("allocations"):
                                parsed["portfolio_stocks"] = []
                                for a in parsed["allocations"]:
                                    ticker = a.get("ticker", "")
                                    weight = a.get("weight", 0)
                                    rationale = a.get("rationale", "")
                                    # Extract entry price from rationale if present
                                    entry_match = re.search(r'Entry[:\s]+([^;\n]+)', rationale)
                                    entry_price = entry_match.group(1).strip() if entry_match else None
                                    # Extract target from rationale if present
                                    target_match = re.search(r'Target[:\s]+([^;\n]+)', rationale)
                                    target_price = target_match.group(1).strip() if target_match else None
                                    # Extract stop from rationale if present
                                    stop_match = re.search(r'Stop[:\s]+([^;\n]+)', rationale)
                                    stop_loss = stop_match.group(1).strip() if stop_match else None
                                    parsed["portfolio_stocks"].append({
                                        "ticker": ticker,
                                        "allocation_pct": weight,
                                        "rationale": rationale,
                                        "entry_price": entry_price,
                                        "target_price": target_price,
                                        "stop_loss": stop_loss,
                                    })
                            if not parsed.get("scenario_analysis") and parsed.get("scenarios"):
                                parsed["scenario_analysis"] = []
                                scenario_colors = {"Bull": "#22c55e", "Base": "#6366f1", "Bear": "#ef4444"}
                                for s in parsed["scenarios"]:
                                    label = s.get("label", "")
                                    prob = int(s.get("probability", 0) * 100)
                                    parsed["scenario_analysis"].append({
                                        "label": label,
                                        "probability_pct": prob,
                                        "outcome": s.get("target", ""),
                                        "description": s.get("thesis", ""),
                                        "color": scenario_colors.get(label, "#6366f1"),
                                    })
                            if not parsed.get("allocation_breakdown") and parsed.get("allocations"):
                                parsed["allocation_breakdown"] = []
                                for a in parsed["allocations"]:
                                    parsed["allocation_breakdown"].append({
                                        "label": a.get("ticker", ""),
                                        "percentage": a.get("weight", 0),
                                        "rationale": a.get("rationale", ""),
                                    })
                            if not parsed.get("market_context"):
                                parsed["market_context"] = []
                            if not parsed.get("action_prompts"):
                                parsed["action_prompts"] = []
                            # Allocation sum check
                            alloc = parsed.get("allocation_breakdown") or []
                            if alloc:
                                total = sum(float(a.get("percentage", 0)) for a in alloc)
                                if abs(total - 100.0) > 1.0:
                                    parsed.setdefault("data_quality_flags", [])
                                    parsed["data_quality_flags"].append(f"Allocation sums to {total:.1f}% (expected 100%)")
                            # Scenario count check
                            scenarios = parsed.get("scenario_analysis") or []
                            if len(scenarios) < 3:
                                parsed.setdefault("data_quality_flags", [])
                                parsed["data_quality_flags"].append("Scenario analysis incomplete")
                            # Validate portfolio stock data against real yfinance
                            if parsed.get("portfolio_stocks"):
                                pf_market = _infer_portfolio_market(parsed["portfolio_stocks"], stream_market)
                                corrected_stocks, corrected_summary, pf_corrections = await asyncio.to_thread(
                                    validate_portfolio_stocks, parsed["portfolio_stocks"], pf_market, parsed.get("summary", "")
                                )
                                parsed["portfolio_stocks"] = corrected_stocks
                                if corrected_summary != parsed.get("summary", ""):
                                    parsed["summary"] = corrected_summary
                                if pf_corrections and parsed.get("summary"):
                                    parsed["summary"] += f" [Data verified: {'; '.join(pf_corrections)}]"
                                # Fill live prices for entry/target/stop_loss
                                pf_market = _infer_portfolio_market(parsed["portfolio_stocks"], stream_market)
                                filled_stocks, fill_notes = await asyncio.to_thread(
                                    _validate_and_fill_portfolio_prices, parsed["portfolio_stocks"], pf_market
                                )
                                parsed["portfolio_stocks"] = filled_stocks
                                if fill_notes and parsed.get("summary"):
                                    parsed["summary"] += f" [Live prices verified: {'; '.join(fill_notes)}]"
                        result_holder["result"] = StructuredQueryResponse(**parsed)
                        # Validate LLM metrics against injected [VERIFIED] data
                        verified = extract_verified_values(result_holder.get("platform_ctx"))
                        _, result_holder["result"].summary, _ = validate_response(
                            result_holder["result"].metrics or [],
                            result_holder["result"].summary or "",
                            verified,
                        )
                        # Mark as Morgan report if classified
                        if _is_report_stream:
                            result_holder["result"].is_report = True
                        # Attach stock summary from enrichment data
                        result_holder["result"].stock_summary = _build_stock_summary(
                            stream_ticker, stream_market,
                            result_holder.get("enrichment", {}),
                            result_holder.get("platform_ctx"),
                        )
                        # Persist conversation turn (best-effort, streaming)
                        if user_id_stream and req.session_key:
                            try:
                                await asyncio.to_thread(
                                    _save_conversation_turn, user_id_stream, req.session_key,
                                    "user", req.question, stream_ticker, stream_market
                                )
                                await asyncio.to_thread(
                                    _save_conversation_turn, user_id_stream, req.session_key,
                                    "assistant", result_holder["result"].summary, stream_ticker, stream_market
                                )
                            except Exception:
                                pass
                    except (ValidationError, Exception) as e:
                        log.warning("Tool-use structured output validation failed: %s", e)

                # Fallback path — if tool_use missed (extremely rare with tool_choice forced),
                # extract from any text block and run the markdown salvage parser.
                if "result" not in result_holder:
                    raw = ""
                    for block in response.content:
                        if getattr(block, "type", None) == "text":
                            raw = block.text
                            break
                    freeform_resp = _parse_query_response(raw, route)
                    result_holder["result"] = _structured_from_markdown(
                        raw, freeform_resp, route,
                        _build_stock_summary(stream_ticker, stream_market, result_holder.get("enrichment", {}), result_holder.get("platform_ctx")),
                    )
                    # Validate LLM metrics against injected [VERIFIED] data
                    verified = extract_verified_values(result_holder.get("platform_ctx"))
                    _, result_holder["result"].summary, _ = validate_response(
                        result_holder["result"].metrics or [],
                        result_holder["result"].summary or "",
                        verified,
                    )
            except anthropic.APITimeoutError:
                result_holder["result"] = StructuredQueryResponse(
                    verdict="HOLD", confidence=0, timeframe="Medium-term",
                    summary="Query timed out — the AI took too long to respond. Try a shorter question.",
                    reasoning=ReasoningBlock(why_this="N/A",why_not_alt="N/A",edge_summary="N/A",second_best="N/A",confidence_gap="N/A"),
                    route=route,
                )
            except Exception as exc:
                result_holder["result"] = StructuredQueryResponse(
                    verdict="HOLD", confidence=0, timeframe="Medium-term",
                    summary=f"Query failed: {str(exc)[:200]}",
                    reasoning=ReasoningBlock(why_this="N/A",why_not_alt="N/A",edge_summary="N/A",second_best="N/A",confidence_gap="N/A"),
                    route=route,
                )
            finally:
                llm_done.set()

        llm_task = asyncio.create_task(_call_llm())
        llm_start = time.monotonic()
        # Emit thinking → generate phase transitions while LLM works
        sent_thinking = False
        sent_generate = False
        while not llm_done.is_set():
            yield 'data: {"status":"running"}\n\n'
            llm_elapsed = time.monotonic() - llm_start
            if not sent_thinking and llm_elapsed > 1.5:
                yield f'data: {_json.dumps({"status":"phase","phase":"thinking","label":_PHASE_LABELS["thinking"]})}\n\n'
                sent_thinking = True
            if not sent_generate and llm_elapsed > 12:
                yield f'data: {_json.dumps({"status":"phase","phase":"generate","label":_PHASE_LABELS["generate"]})}\n\n'
                sent_generate = True
            total_elapsed = time.monotonic() - query_start
            if total_elapsed > 180:                 # bumped 60s -> 180s total cap
                llm_task.cancel()
                result_holder.setdefault("result", StructuredQueryResponse(
                    verdict="HOLD", confidence=0, timeframe="Medium-term",
                    summary="Analysis timed out after 3 minutes. Try a shorter or more specific question.",
                    reasoning=ReasoningBlock(why_this="N/A",why_not_alt="N/A",edge_summary="N/A",second_best="N/A",confidence_gap="N/A"),
                    route=route,
                ))
                llm_done.set()
                break
            try:
                await asyncio.wait_for(asyncio.shield(llm_done.wait()), timeout=4.0)
            except asyncio.TimeoutError:
                pass

        # Final phases: parse + render
        yield f'data: {_json.dumps({"status":"phase","phase":"parse","label":_PHASE_LABELS["parse"]})}\n\n'
        yield f'data: {_json.dumps({"status":"phase","phase":"render","label":_PHASE_LABELS["render"]})}\n\n'

        if "result" in result_holder:
            yield f'data: {_json.dumps({"status":"done","result": result_holder["result"].model_dump()})}\n\n'
        else:
            yield f'data: {_json.dumps({"status":"error","message":"No result produced"})}\n\n'
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
