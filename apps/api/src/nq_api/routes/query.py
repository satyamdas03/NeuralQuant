"""POST /query — natural language financial query endpoint."""
import os
import re
from datetime import date

import anthropic
import yfinance as yf
from fastapi import APIRouter
from nq_api.schemas import QueryRequest, QueryResponse

router = APIRouter()

MODEL = "claude-sonnet-4-20250514"

_STOP_WORDS = {
    "WHAT", "WHEN", "WHERE", "WILL", "HAVE", "DOES", "WERE", "THAN",
    "THAT", "WITH", "FROM", "THIS", "THEY", "BEEN", "ALSO", "SOME",
    "INTO", "OVER", "AFTER", "WOULD", "COULD", "ABOUT", "WHICH",
    "CAUSE", "EFFECT", "IMPACT", "STOCK", "STOCKS",
}

# Keyword → sector ETF / representative tickers for news injection
_SECTOR_MAP: dict[str, list[str]] = {
    "OIL":      ["XLE", "XOM", "CVX"],
    "ENERGY":   ["XLE", "XOM", "CVX"],
    "GAS":      ["XLE", "UNG"],
    "CRUDE":    ["XLE", "XOM"],
    "IRAN":     ["XLE", "XOM", "^GSPC"],
    "WAR":      ["^GSPC", "XLE", "GLD"],
    "GEOPOLIT": ["^GSPC", "GLD"],
    "TECH":     ["XLK", "NVDA", "AAPL"],
    "AI":       ["XLK", "NVDA", "MSFT"],
    "RATE":     ["^TNX", "XLF", "TLT"],
    "FED":      ["^TNX", "XLF", "SPY"],
    "GOLD":     ["GLD", "GDX"],
    "CRYPTO":   ["BTC-USD", "ETH-USD"],
    "BITCOIN":  ["BTC-USD"],
    "BANK":     ["XLF", "JPM", "BAC"],
    "PHARMA":   ["XLV", "JNJ", "PFE"],
    "INDIA":    ["INDA", "^BSESN"],
    "NSE":      ["INDA", "^BSESN"],
}

_SYSTEM = """You are NeuralQuant's financial intelligence assistant.
Today's date and recent market news headlines are injected at the top of every user message.
Use them as your primary source of truth for current events.

Rules:
1. ALWAYS use the injected "Today's date" and "Recent headlines" for any current-events question.
2. If relevant headlines are provided, answer based on them — never say "I have no data".
3. If the event is clearly after your training cutoff AND no headlines cover it, acknowledge the
   current date, reference any relevant headlines you have, then give the best analysis from
   first principles. NEVER give a historical answer when a current question is asked.
4. End every response with exactly 3 follow-up questions the user might want answered.
5. Cite which sources informed your answer.
6. Be direct. Financial professionals read this.

Response format:
ANSWER: [Your answer]
DATA_SOURCES: [comma-separated list]
FOLLOW_UP:
- [Question 1]
- [Question 2]
- [Question 3]"""


def _fetch_relevant_news(question: str, ticker: str | None, n: int = 8) -> list[str]:
    """Pull recent headlines from yfinance for context injection."""
    # Always start with broad market + any user-specified ticker
    priority: list[str] = ["^GSPC", "SPY"]
    if ticker:
        priority.insert(0, ticker)

    # Detect sector keywords and inject the right ETFs/tickers
    q_upper = question.upper()
    for keyword, syms in _SECTOR_MAP.items():
        if keyword in q_upper:
            for s in syms:
                if s not in priority:
                    priority.append(s)

    # Also try any short words that look like real tickers (2-5 alpha chars, not stop-words)
    extra: list[str] = []
    for word in q_upper.split():
        clean = re.sub(r"[^A-Z]", "", word)
        if 2 <= len(clean) <= 5 and clean not in _STOP_WORDS and clean not in priority:
            extra.append(clean)

    candidates = priority + extra

    headlines: list[str] = []
    seen: set[str] = set()
    for sym in candidates[:8]:  # try up to 8 sources
        try:
            items = yf.Ticker(sym).news or []
            for item in items[:3]:
                content = item.get("content") or {}
                title = content.get("title") or item.get("title", "")
                publisher = (
                    (content.get("provider") or {}).get("displayName")
                    or item.get("publisher", "")
                )
                if title and title not in seen:
                    seen.add(title)
                    label = f"[{publisher}] {title}" if publisher else title
                    headlines.append(label)
        except Exception:
            pass
        if len(headlines) >= n:
            break
    return headlines[:n]


@router.post("", response_model=QueryResponse)
def run_nl_query(req: QueryRequest) -> QueryResponse:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return QueryResponse(
            answer="Query service unavailable: ANTHROPIC_API_KEY not configured.",
            data_sources=[],
            follow_up_questions=[],
        )
    client = anthropic.Anthropic(api_key=api_key)

    today = date.today().strftime("%B %d, %Y")
    headlines = _fetch_relevant_news(req.question, req.ticker)

    context_parts = [
        f"Today's date: {today}",
        f"User question: {req.question}",
    ]
    if req.ticker:
        context_parts.append(f"Stock in focus: {req.ticker} ({req.market or 'US'} market)")
    if headlines:
        context_parts.append("Recent market headlines (use these to answer current-events questions):")
        for h in headlines:
            context_parts.append(f"  • {h}")

    user_msg = "\n".join(context_parts)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text
        return _parse_query_response(raw)
    except Exception as exc:
        return QueryResponse(
            answer=f"Query failed: {str(exc)[:100]}",
            data_sources=[],
            follow_up_questions=[],
        )


def _parse_query_response(raw: str) -> QueryResponse:
    answer_match = re.search(r"ANSWER:\s*(.+?)(?=DATA_SOURCES:|\Z)", raw, re.I | re.S | re.M)
    answer = answer_match.group(1).strip() if answer_match else raw[:500]

    sources_match = re.search(r"DATA_SOURCES:\s*(.+?)(?=FOLLOW_UP:|\Z)", raw, re.I | re.S | re.M)
    sources = [s.strip() for s in sources_match.group(1).split(",")] if sources_match else []

    followup_match = re.search(r"FOLLOW_UP:(.*)", raw, re.I | re.S | re.M)
    followups = []
    if followup_match:
        followups = [
            re.sub(r"^[-*•]\s*|\d+\.\s*", "", q.strip()).strip()
            for q in followup_match.group(1).strip().splitlines()
            if q.strip() and q.strip() not in ("-", "*", "•")
        ]

    return QueryResponse(
        answer=answer[:2000],
        data_sources=sources[:5],
        follow_up_questions=followups[:3],
    )
