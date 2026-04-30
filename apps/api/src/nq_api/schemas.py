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
    preset: Optional[str] = None         # "momentum_breakout", "value_play", etc.
    min_momentum: Optional[float] = None  # 0-100 percentile filter
    min_quality: Optional[float] = None
    min_low_vol: Optional[float] = None
    max_momentum: Optional[float] = None


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
    route: Literal["SNAP", "REACT", "DEEP"] = "REACT"


# ── Structured Query Response (v2) ──────────────────────────────────────────

class MetricItem(BaseModel):
    name: str
    value: str
    benchmark: str | None = None
    status: Literal["positive", "negative", "neutral"]

class ScenarioItem(BaseModel):
    label: str          # "Bear" / "Base" / "Bull"
    probability: float   # 0-1
    target: str         # "$185" or "₹4,200"
    thesis: str         # one-line trigger

class AllocationItem(BaseModel):
    ticker: str
    weight: float        # percentage 0-100
    rationale: str       # why THIS stock
    why_not_alt: str     # why not the next-best alternative

class ComparisonItem(BaseModel):
    ticker: str
    metric: str         # "P/E", "Revenue Growth", "ForeCast Score"
    ours: str           # the recommended stock's value
    theirs: str         # the alternative's value
    edge: str           # one-line why ours wins on this metric

class ReasoningBlock(BaseModel):
    why_this: str        # Why we chose X — specific data-driven justification
    why_not_alt: str     # Why not the next-best alternative Y — with data
    edge_summary: str    # One-line edge statement: "X wins on [metric] vs Y"
    second_best: str     # Name of the runner-up stock we rejected
    confidence_gap: str  # How much better X is than Y (e.g. "Score 8 vs 6, +2 edge")

class StructuredQueryResponse(BaseModel):
    verdict: str                              # STRONG BUY | BUY | HOLD | SELL | STRONG SELL
    confidence: float                         # 0-100
    timeframe: str                            # Short-term | Medium-term | Long-term
    summary: str                              # 4-8 sentence detailed summary with data points
    metrics: list[MetricItem] = []
    reasoning: ReasoningBlock                 # comparative reasoning — why X not Y
    scenarios: list[ScenarioItem] = []
    allocations: list[AllocationItem] = []    # portfolio questions only
    comparisons: list[ComparisonItem] = []     # DEEP route or compare questions
    data_sources: list[str] = []
    follow_up_questions: list[str] = []
    route: Literal["SNAP", "REACT", "DEEP"] = "REACT"
