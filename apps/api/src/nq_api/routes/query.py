"""POST /query — natural language financial query endpoint."""
import os
import re

import anthropic
from fastapi import APIRouter
from nq_api.schemas import QueryRequest, QueryResponse

router = APIRouter()

_SYSTEM = """You are NeuralQuant's financial intelligence assistant.
You answer questions about stocks, markets, and financial concepts using the data provided.

Rules:
1. Ground every answer in the provided data. Do NOT invent numbers.
2. If data is insufficient, say so and explain what would be needed.
3. End every response with exactly 3 follow-up questions the user might want answered.
4. Cite which data sources informed your answer.
5. Be direct. Financial professionals read this.

Response format:
ANSWER: [Your answer]
DATA_SOURCES: [comma-separated list: e.g., "NeuralQuant AI Score, FRED macro data, Phase 1 signal engine"]
FOLLOW_UP:
- [Question 1]
- [Question 2]
- [Question 3]"""


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

    context_parts = [f"User question: {req.question}"]
    if req.ticker:
        context_parts.append(f"Stock in focus: {req.ticker} ({req.market} market)")
        context_parts.append("Note: Real-time data will be injected here in Phase 3.")

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
    answer_match = re.search(r"ANSWER:\s*(.+?)(?=DATA_SOURCES:|\Z)", raw, re.I | re.S)
    answer = answer_match.group(1).strip() if answer_match else raw[:500]

    sources_match = re.search(r"DATA_SOURCES:\s*(.+?)(?=FOLLOW_UP:|\Z)", raw, re.I | re.S)
    sources = [s.strip() for s in sources_match.group(1).split(",")] if sources_match else []

    followup_match = re.search(r"FOLLOW_UP:(.*)", raw, re.I | re.S)
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
