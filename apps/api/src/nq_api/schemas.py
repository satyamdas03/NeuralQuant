# apps/api/src/nq_api/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal


class FeatureDriver(BaseModel):
    name: str
    contribution: float          # positive = bullish, negative = bearish
    value: str                   # human-readable value ("P/E: 18.2")
    direction: Literal["positive", "negative", "neutral"]


class SubScores(BaseModel):
    quality: float               # 0-1
    momentum: float              # 0-1
    short_interest: float        # 0-1
    value: float                 # 0-1 (0.5 = neutral placeholder)
    low_vol: float               # 0-1 (0.5 = neutral placeholder)
    insider: float = 0.5         # 0-1 (EDGAR Form 4 cluster score, US only)


class AIScore(BaseModel):
    ticker: str
    market: Literal["US", "IN", "GLOBAL"]
    composite_score: float       # 0-1
    score_1_10: int              # 1-10 for display
    regime_id: int               # 1-4
    regime_label: str            # "Risk-On" / "Late-Cycle" / "Bear" / "Recovery"
    sub_scores: SubScores
    top_drivers: list[FeatureDriver]  # top 5 positive + negative features
    confidence: Literal["high", "medium", "low"]
    last_updated: str            # ISO datetime


class ScreenerRequest(BaseModel):
    market: Literal["US", "IN", "GLOBAL"] = "US"
    min_score: float = 0.0
    max_results: int = Field(50, le=200)
    tickers: Optional[list[str]] = None  # if None, use default universe


class ScreenerResponse(BaseModel):
    regime_label: str
    regime_id: int
    results: list[AIScore]
    total: int


class AgentOutput(BaseModel):
    agent: str                   # "MACRO", "FUNDAMENTAL", etc.
    stance: Literal["BULL", "BEAR", "NEUTRAL"]
    conviction: Literal["HIGH", "MEDIUM", "LOW"]
    thesis: str                  # 2-3 sentence argument
    key_points: list[str]        # 3-5 bullet points


class AnalystRequest(BaseModel):
    ticker: str
    market: Literal["US", "IN", "GLOBAL"] = "US"
    include_adversarial: bool = True


class AnalystResponse(BaseModel):
    ticker: str
    head_analyst_verdict: str    # STRONG BUY / BUY / HOLD / SELL / STRONG SELL
    investment_thesis: str       # 4-6 sentence synthesis
    bull_case: str
    bear_case: str
    risk_factors: list[str]
    agent_outputs: list[AgentOutput]
    consensus_score: float       # weighted average of agent conviction scores


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class QueryRequest(BaseModel):
    question: str
    ticker: Optional[str] = None
    market: Literal["US", "IN", "GLOBAL"] = "US"
    history: list[ConversationMessage] = []  # previous turns for multi-turn chat


class QueryResponse(BaseModel):
    answer: str
    data_sources: list[str]      # which data was used to answer
    follow_up_questions: list[str]  # 3 suggested follow-ups
