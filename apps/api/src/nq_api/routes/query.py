"""POST /query — natural language financial query endpoint."""
import os
import re
from datetime import date

import anthropic
import yfinance as yf
from fastapi import APIRouter
from nq_api.schemas import QueryRequest, QueryResponse

router = APIRouter()

_STOP_WORDS = {
    "WHAT", "WHEN", "WHERE", "WILL", "HAVE", "DOES", "WERE", "THAN",
    "THAT", "WITH", "FROM", "THIS", "THEY", "BEEN", "ALSO", "SOME",
    "INTO", "OVER", "AFTER", "WOULD", "COULD", "ABOUT", "WHICH",
}

_SYSTEM = """You are NeuralQuant's financial intelligence assistant.
Today's date and recent market news headlines are injected at the top of every user message.
Use them as your primary source of truth for current events.

Rules:
1. ALWAYS use the injected "Today's date" and "Recent headlines" for any current-events question.
2. If relevant headlines are provided, answer based on them — never say "I have no data".
3. If the event is clearly after your training cutoff AND no headlines cover it, say so briefly,
   then give the best analysis you can from first principles and the headlines available.
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


def _fetch_relevant_news(question: str, ticker: str | None, n: int = 6) -> list[str]:
    """Pull recent headlines from yfinance for context injection."""
    candidates: list[str] = []
    if ticker:
        candidates.append(ticker)
    for word in question.upper().split():
        clean = re.sub(r"[^A-Z]", "", word)
        if 2 <= len(clean) <= 5 and clean not in _STOP_WORDS:
            candidates.append(clean)
    candidates += ["^GSPC", "SPY"]

    headlines: list[str] = []
    seen: set[str] = set()
    for sym in candidates[:5]:
        try:
            items = yf.Ticker(sym).news or []
            for item in items[:4]:
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
            model="claude-sonnet-4-6",
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
