"""Text parsing, ticker detection, JSON extraction, and response formatting."""
import json as _json
import logging
import re

from nq_api.services.constants import (
    _STOP_WORDS, _TICKER_STOP_WORDS, _INDIA_KEYWORDS,
    _NSE_NAME_MAP, _SCREENER_KEYWORDS,
)
from nq_api.schemas import (
    QueryResponse, MetricItem, ScenarioItem,
    ReasoningBlock, ComparisonItem, StockSummary,
)

log = logging.getLogger(__name__)


def _detect_tickers_in_question(question: str, market: str = "US") -> tuple[list[str], list[str]]:
    """
    Returns (in_universe_tickers, out_of_universe_words).
    in_universe_tickers: known tickers found in question.
    out_of_universe_words: words that look like NSE tickers but aren't in universe.
    """
    from nq_api.universe import US_DEFAULT, IN_DEFAULT
    known_us = set(US_DEFAULT)
    known_in = set(IN_DEFAULT)
    in_universe = []
    q_upper = question.upper()

    # Check known universe tickers -- skip single-letter tickers (A, T, F, etc.)
    # to avoid false positives from common English words.
    # When market=IN, only check Indian tickers.
    search_pool = known_in if market == "IN" else (known_us | known_in)
    in_tickers: list[str] = []
    us_matches: list[str] = []
    for t in search_pool:
        base = t.replace(".NS", "").replace(".BO", "")
        if len(base) <= 2:
            continue  # single/double-letter tickers match too many English words
        if base in _TICKER_STOP_WORDS:
            continue  # common English word that happens to be a ticker (e.g. NOW)
        if re.search(r'\b' + re.escape(base) + r'\b', q_upper):
            in_tickers.append(t)
            if t in known_in:
                in_universe.append(t)
            elif t in known_us:
                us_matches.append(t)
    # IN tickers first (user intent more likely for direct ticker matches),
    # then US tickers. Avoids non-deterministic set iteration picking wrong ticker.
    in_universe.extend(us_matches)

    # For India queries, also check NSE name map keys
    out_of_universe = []
    known_bases = {t.replace(".NS", "").replace(".BO", "") for t in search_pool}
    if market == "IN" or any(k in q_upper for k in _INDIA_KEYWORDS):
        # First check the name map directly
        for name_key in _NSE_NAME_MAP:
            if (re.search(r'\b' + re.escape(name_key) + r'\b', q_upper)
                    and name_key not in known_bases):
                if name_key not in out_of_universe:
                    out_of_universe.append(name_key)

        # Then scan remaining words that look like tickers
        for word in q_upper.split():
            clean = re.sub(r"[^A-Z]", "", word)
            if (3 <= len(clean) <= 12
                    and clean not in _STOP_WORDS
                    and clean not in _TICKER_STOP_WORDS
                    and clean not in known_bases
                    and clean not in out_of_universe
                    and clean not in _NSE_NAME_MAP):
                out_of_universe.append(clean)

    return in_universe[:5], out_of_universe[:3]


def _fmt_price_row(ticker: str, fund: dict, score: int, market: str, rank: int | None = None) -> str:
    """Format a single stock row with LIVE price + score for LLM context injection."""
    is_india = market == "IN" or ticker.endswith(".NS") or ticker.endswith(".BO")
    cur = "Rs." if is_india else "$"  # ASCII-safe currency symbol

    price    = fund.get("current_price")
    low52    = fund.get("week52_low")
    high52   = fund.get("week52_high")
    target   = fund.get("analyst_target")
    rec      = fund.get("analyst_rec", "")
    chg      = fund.get("change_pct", 0.0)
    pe       = fund.get("pe_ttm")
    pb       = fund.get("pb_ratio")
    name     = fund.get("long_name", ticker)
    mcap     = fund.get("market_cap")

    price_str  = f"{cur}{price:,.2f} ({chg:+.1f}%)" if price else "price N/A"
    range_str  = f"52w {cur}{low52:,.0f}-{cur}{high52:,.0f}" if low52 and high52 else ""
    target_str = f"analyst target {cur}{target:,.0f} ({rec})" if target else ""
    pe_str     = f"P/E={pe:.1f}" if pe else ""
    mcap_str   = ""
    if mcap:
        if is_india:
            mcap_str = f"MCap={mcap/1e7:.0f}Cr"
        else:
            mcap_str = f"MCap=${mcap/1e9:.0f}B" if mcap >= 1e9 else f"MCap=${mcap/1e6:.0f}M"

    prefix = f"#{rank} " if rank else "  "
    details = " | ".join(x for x in [range_str, pe_str, mcap_str, target_str] if x)
    return f"{prefix}{ticker} ({name}): {score}/10 | {price_str} | {details}"


def _parse_query_response(raw: str, route: str = "REACT") -> QueryResponse:
    # Strip markdown bold around section headers (Claude occasionally wraps
    # `ANSWER:` as `**ANSWER:**`), which previously leaked `**` into the
    # answer text and data_sources list. Normalize BEFORE regex splits.
    norm = re.sub(r"\*\*\s*(ANSWER|DATA_SOURCES|FOLLOW_UP)\s*:\s*\*\*", r"\1:", raw, flags=re.I)

    answer_match = re.search(r"ANSWER:\s*(.+?)(?=DATA_SOURCES:|\Z)", norm, re.I | re.S | re.M)
    answer = answer_match.group(1).strip() if answer_match else norm[:8000]

    sources_match = re.search(r"DATA_SOURCES:\s*(.+?)(?=FOLLOW_UP:|\Z)", norm, re.I | re.S | re.M)
    sources_raw = sources_match.group(1) if sources_match else ""
    # Strip any leftover `**` from individual source tokens and drop empties.
    sources = [
        re.sub(r"\*+", "", s).strip()
        for s in sources_raw.split(",")
    ]
    sources = [s for s in sources if s and s not in ("-", "*")]

    followup_match = re.search(r"FOLLOW_UP:(.*)", norm, re.I | re.S | re.M)
    followups: list[str] = []
    if followup_match:
        followups = [
            re.sub(r"^[-*o]\s*|\d+\.\s*", "", q.strip()).strip().strip("*").strip()
            for q in followup_match.group(1).strip().splitlines()
            if q.strip() and q.strip() not in ("-", "*", "o")
        ]
        followups = [q for q in followups if q]

    return QueryResponse(
        answer=answer[:8000],
        data_sources=sources[:5],
        follow_up_questions=followups[:3],
        route=route,
    )


def _extract_json_from_llm(text: str) -> dict | None:
    """Try to extract a JSON object from LLM output (may be wrapped in markdown or garbled)."""
    import json as _json

    cleaned = text.strip()

    # Strategy 1: Direct parse (clean JSON)
    try:
        return _json.loads(cleaned)
    except (_json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: Remove markdown code fences (```json ... ```)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        try:
            return _json.loads(fence_match.group(1))
        except (_json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: Find JSON object boundaries (first { to last })
    first_brace = cleaned.find("{")
    if first_brace >= 0:
        # Walk through string counting braces to find matching close
        depth = 0
        for i in range(first_brace, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return _json.loads(cleaned[first_brace : i + 1])
                    except (_json.JSONDecodeError, ValueError):
                        break

    # Strategy 4: Aggressive -- strip all markdown, find anything JSON-like
    aggressive = re.sub(r"```(?:json)?\s*", "", cleaned)
    aggressive = re.sub(r"\s*```", "", aggressive)
    aggressive = re.sub(r"\*\*[^*]+\*\*", "", aggressive)  # remove markdown bold
    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        match = re.search(pattern, aggressive)
        if match:
            try:
                return _json.loads(match.group())
            except (_json.JSONDecodeError, ValueError):
                continue

    # Strategy 5: Truncated JSON -- close open braces/brackets and retry
    # Common when max_tokens is hit mid-response
    first_brace = cleaned.find("{")
    if first_brace >= 0:
        snippet = cleaned[first_brace:]
        # Count unclosed braces and brackets
        open_braces = snippet.count("{") - snippet.count("}")
        open_brackets = snippet.count("[") - snippet.count("]")
        if open_braces > 0 or open_brackets > 0:
            repaired = snippet + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
            try:
                return _json.loads(repaired)
            except (_json.JSONDecodeError, ValueError):
                pass
    return None


def _extract_tool_use_input(response) -> dict | None:
    """Pull the tool_use input dict from an Anthropic response. Returns None
    if the model returned text/no tool_use (e.g. on tool_choice rejection)."""
    from nq_api.services.prompts import _STRUCTURED_TOOL
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _STRUCTURED_TOOL["name"]:
            inp = getattr(block, "input", None)
            if isinstance(inp, dict):
                return inp
    return None


def _structured_from_markdown(raw: str, freeform_resp: QueryResponse, route: str, stock_summary: StockSummary | None = None) -> "StructuredQueryResponse":
    """Convert freeform markdown LLM output into a rich StructuredQueryResponse.
    Called when JSON parsing fails -- extracts verdict, metrics, scenarios, etc.
    from the markdown text so the frontend card components have real data."""
    from nq_api.schemas import StructuredQueryResponse

    # Extract verdict from text
    verdict = "HOLD"
    verdict_map = {"STRONG BUY": "STRONG BUY", "BUY": "BUY", "HOLD": "HOLD", "SELL": "SELL", "STRONG SELL": "STRONG SELL"}
    for v in verdict_map:
        if re.search(rf"\b{re.escape(v)}\b", raw, re.I):
            verdict = verdict_map[v]
            break

    # Extract metrics from markdown tables or inline data
    metrics: list[MetricItem] = []
    # Look for patterns like "P/E: 30.8" or "Momentum: 92%" or "| P/E | 30.8 |"
    metric_patterns = [
        (r"P/E[^|]*?(?:[:|]\s*)([\d.]+)", "P/E (TTM)", "Sector avg"),
        (r"Momentum[^|]*?(?:[:|]\s*)([\d.]+)%?", "Momentum", "50% avg"),
        (r"Quality[^|]*?(?:[:|]\s*)([\d.]+)%?", "Quality", "50% avg"),
        (r"ForeCast[^|]*?(?:[:|]\s*)([\d.]+)/10", "ForeCast Score", "5/10 avg"),
        (r"Value[^|]*?(?:[:|]\s*)([\d.]+)%?", "Value", "50% avg"),
        (r"Beta[^|]*?(?:[:|]\s*)([\d.]+)", "Beta", "1.0 avg"),
    ]
    for pattern, name, benchmark in metric_patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            val = m.group(1)
            try:
                float(val)  # validate it's a number
                status = "positive" if name in ("Momentum", "Quality", "Value", "ForeCast Score") and float(val) > 50 else "neutral"
                if name == "P/E (TTM)":
                    status = "negative" if float(val) > 35 else "positive"
                metrics.append(MetricItem(name=name, value=val, benchmark=benchmark, status=status))
            except ValueError:
                pass

    # Extract scenarios (Bear/Base/Bull)
    scenarios: list[ScenarioItem] = []
    scenario_patterns = [
        (r"(?:[\U0001F43B]\s*)?Bear[^:]*?[:\-]\s*[^$%]*?([\$₹][\d,.]+|\-?\d+%)[^()]*?(?:\(([^)]+)\))?", "Bear", 0.20),
        (r"(?:[\U0001F4CA]\s*)?Base[^:]*?[:\-]\s*[^$%]*?([\$₹][\d,.]+|\+?\d+%)[^()]*?(?:\(([^)]+)\))?", "Base", 0.50),
        (r"(?:[\U0001F402]\s*)?Bull[^:]*?[:\-]\s*[^$%]*?([\$₹][\d,.]+|\+?\d+%)[^()]*?(?:\(([^)]+)\))?", "Bull", 0.30),
    ]
    for pattern, label, prob in scenario_patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            target = m.group(1) or ""
            thesis = m.group(2) or ""
            scenarios.append(ScenarioItem(label=label, probability=prob, target=target, thesis=thesis))

    # Extract reasoning sections
    why_this = ""
    why_not_alt = ""
    edge_summary = ""
    second_best = "N/A"
    confidence_gap = "N/A"

    # Look for "Why" sections
    why_match = re.search(r"(?:Why|Why This|Why GOOGL)[^:]*?:\s*(.+?)(?=\n\n|\n(?:Why Not|vs|Bear|Bull|Base|Risk|Scenario|Price|Stop|$))", raw, re.I | re.S)
    if why_match:
        why_this = why_match.group(1).strip()[:300]

    # Look for "Why not" / "vs" / comparison sections
    why_not_match = re.search(r"(?:Why Not|vs\.?|versus|Alternative|compared to)[^:]*?:\s*(.+?)(?=\n\n|\n(?:Why|Bear|Bull|Base|Risk|Scenario|Price|Stop|Macro|$))", raw, re.I | re.S)
    if why_not_match:
        why_not_alt = why_not_match.group(1).strip()[:300]

    # Extract "vs" comparisons for second_best
    vs_match = re.search(r"vs\.?\s+([A-Z]{1,5}(?:\.NS)?)", raw)
    if vs_match:
        second_best = vs_match.group(1)

    # Extract comparison data from tables or inline
    comparisons: list[ComparisonItem] = []
    # Look for "ours vs theirs" patterns or table rows with comparisons
    comp_matches = re.finditer(r"(?:vs\.?|versus|compared to)\s+([A-Z]{1,5}(?:\.NS)?)[^:]*?(?:P/E|momentum|quality|score|value)[^)]*?\)", raw, re.I)
    seen_tickers = set()
    for cm in comp_matches:
        ticker = cm.group(1)
        if ticker not in seen_tickers:
            comparisons.append(ComparisonItem(
                ticker=ticker, metric="Composite", ours="Higher", theirs="Lower",
                edge="Superior ForeCast score and factor alignment"
            ))
            seen_tickers.add(ticker)

    # Build reasoning from extracted data
    if not why_this:
        # Fallback: use first 2-3 sentences of the answer
        first_sentences = re.split(r'[.!?]\s', freeform_resp.answer)[:3]
        why_this = '. '.join(first_sentences) if first_sentences else "See summary for details"

    if not why_not_alt:
        why_not_alt = "Alternative stocks evaluated but this pick showed superior factor alignment"

    if not edge_summary:
        edge_summary = "Selected based on strongest combined score and factor alignment"

    # Determine confidence from verdict
    confidence = {"STRONG BUY": 85, "BUY": 70, "HOLD": 50, "SELL": 70, "STRONG SELL": 85}.get(verdict, 50)

    # Extract timeframe from question
    timeframe = "Medium-term"
    q_lower = (freeform_resp.answer + " ").lower()
    if any(w in q_lower for w in ["next month", "1 month", "short term", "short-term", "weeks"]):
        timeframe = "Short-term"
    elif any(w in q_lower for w in ["long term", "long-term", "year", "years", "5 year"]):
        timeframe = "Long-term"

    # Strip markdown so the summary <p> doesn't render raw `#` and `**` chars.
    clean_summary = re.sub(r"^#+\s*", "", freeform_resp.answer, flags=re.M)  # strip headers
    clean_summary = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean_summary)          # strip bold
    clean_summary = re.sub(r"^[-*]\s+", "• ", clean_summary, flags=re.M)      # bullets
    clean_summary = re.sub(r"^---+$", "", clean_summary, flags=re.M)          # rules
    clean_summary = re.sub(r"\n{3,}", "\n\n", clean_summary).strip()

    return StructuredQueryResponse(
        verdict=verdict,
        confidence=confidence,
        timeframe=timeframe,
        summary=clean_summary[:800],
        metrics=metrics[:6],
        reasoning=ReasoningBlock(
            why_this=why_this,
            why_not_alt=why_not_alt,
            edge_summary=edge_summary,
            second_best=second_best,
            confidence_gap=confidence_gap,
        ),
        scenarios=scenarios[:3],
        allocations=[],
        comparisons=comparisons[:4],
        data_sources=freeform_resp.data_sources,
        follow_up_questions=freeform_resp.follow_up_questions,
        route=freeform_resp.route,
        stock_summary=stock_summary,
    )
