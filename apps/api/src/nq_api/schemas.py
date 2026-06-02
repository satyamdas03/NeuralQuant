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
    growth: float = 0.5          # 0-1 (revenue growth YoY percentile)
    insider: float = 0.5         # 0-1 (EDGAR Form 4 cluster score, US only)


class AnjaliScores(BaseModel):
    """Anjali Value Screener quintile scores (-4 to +4 each, composite -16 to +16)."""
    growth_score: float | None = None        # -4 to +4 vs index peers
    return_score: float | None = None        # -4 to +4
    valuation_score: float | None = None     # -4 to +4 (Q2=+1 sweet spot)
    risk_score: float | None = None          # -4 to +4 (Q4=+1 sweet spot)
    composite: float | None = None            # -16 to +16
    g_score: float | None = None            # Quantitative Conviction Score: -12 to +12
    risk_eff_score: float | None = None      # Risk Efficiency Score: -8 to +8
    irs_raw: float | None = None             # IRS raw: -20 to +20
    irs_pct: float | None = None             # IRS %: 0 to 100
    is_loss_making: bool = False              # True if any loss flag set
    valuation_sweet_spot: bool = False        # True if Q2 valuation (score 0.5-1.5)


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
    anjali: AnjaliScores | None = None  # Anjali Value Screener scores (None if not available)


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
    # Anjali Value Screener filters (-16 to +16 composite scale)
    min_anjali_composite: Optional[float] = None  # minimum Anjali composite score
    valuation_sweet_spot: Optional[bool] = None   # True = only Q2 valuation stocks
    loss_making: Optional[bool] = None             # True = exclude loss-making companies


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


class UserProfile(BaseModel):
    risk_profile: str  # conservative | balanced | aggressive
    time_horizon: str  # <1yr | 1-3yr | 3-5yr | 5yr+
    goal: str  # wealth_building | retirement | education | passive_income | tax_saving
    investable_amount: str | None = None
    email_market_wrap: bool = True  # opt-in for daily market wrap emails


class QueryRequest(BaseModel):
    question: str
    ticker: Optional[str] = None
    market: Literal["US", "IN", "GLOBAL"] = "US"
    history: list[ConversationMessage] = []  # previous turns for multi-turn chat
    session_key: Optional[str] = None  # persistent conversation key (client-generated UUID)
    profile: UserProfile | None = None
    clarification_answers: list[str] | None = None  # answers from ClarificationCard
    is_report: bool = False  # True when DART classifies as REPORT (16-section institutional)


class QueryResponse(BaseModel):
    answer: str
    data_sources: list[str]      # which data was used to answer
    follow_up_questions: list[str]  # 3 suggested follow-ups
    route: Literal["SNAP", "REACT", "DEEP"] = "REACT"
    is_report: bool = False      # True if response is a full institutional research report


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

class StockSummary(BaseModel):
    ticker: str
    name: str | None = None
    price: float | None = None
    change_pct: float | None = None
    pe_ttm: float | None = None
    eps_ttm: float | None = None
    pb_ratio: float | None = None
    market_cap: float | None = None
    week_52_high: float | None = None
    week_52_low: float | None = None
    analyst_target: float | None = None
    analyst_recommendation: str | None = None
    beta: float | None = None
    sector: str | None = None
    forecast_score: float | None = None  # 1-10
    currency: str = "$"
    anjali: AnjaliScores | None = None  # Anjali Value Screener scores
    # FMP Premium enrichment fields
    analyst_consensus: str | None = None
    analyst_buy_pct: float | None = None
    analyst_target_avg: float | None = None
    analyst_target_high: float | None = None
    analyst_target_low: float | None = None
    analyst_revenue_est: float | None = None
    analyst_eps_est: float | None = None
    analyst_count: int | None = None
    altman_z_score: float | None = None
    piotroski_score: int | None = None
    insider_buys: int | None = None
    insider_sells: int | None = None
    insider_shares_bought: int | None = None
    insider_shares_sold: int | None = None
    dividend_latest: float | None = None
    dividend_yield_pct: float | None = None
    next_earnings_date: str | None = None
    next_earnings_eps_est: float | None = None
    dcf_value: float | None = None
    # OpenBB enrichment fields
    iv_percentile: float | None = None
    put_call_ratio: float | None = None
    implied_volatility: float | None = None
    yield_curve_2y: float | None = None
    yield_curve_10y: float | None = None
    yield_curve_spread: float | None = None


# ── Portfolio Output Models (Phase 1) ────────────────────────────────────────

class MarketContextCard(BaseModel):
    label: str
    value: str
    change: Optional[str] = None
    sentiment: Optional[str] = None


class AllocationSegment(BaseModel):
    label: str
    percentage: float
    color: Optional[str] = None
    rationale: Optional[str] = None


class PortfolioStockCard(BaseModel):
    ticker: str
    name: Optional[str] = None
    allocation_pct: float
    entry_price: Optional[str] = None
    target_price: Optional[str] = None
    stop_loss: Optional[str] = None
    risk_reward: Optional[str] = None
    rationale: Optional[str] = None
    confidence: Optional[int] = None
    sector: Optional[str] = None
    price_unavailable: Optional[bool] = None


class ScenarioCard(BaseModel):
    label: str
    probability_pct: Optional[int] = None
    outcome: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class ActionPrompt(BaseModel):
    label: str
    prompt_text: str
    icon: Optional[str] = None


class ClarificationQuestion(BaseModel):
    question: str
    options: list[str] = []
    question_type: str  # risk_tolerance | time_horizon | sector_preference | capital | investment_goal | context


class StructuredQueryResponse(BaseModel):
    verdict: str                              # STRONG BUY | BUY | HOLD | SELL | STRONG SELL
    confidence: float                         # 0-100
    timeframe: str                            # Short-term | Medium-term | Long-term
    summary: str                              # 4-8 sentence detailed summary with data points
    stock_summary: StockSummary | None = None  # quick-glance stock data card
    metrics: list[MetricItem] = []
    reasoning: ReasoningBlock                 # comparative reasoning — why X not Y
    scenarios: list[ScenarioItem] = []
    allocations: list[AllocationItem] = []    # portfolio questions only
    comparisons: list[ComparisonItem] = []     # DEEP route or compare questions
    data_sources: list[str] = []
    follow_up_questions: list[str] = []
    route: Literal["SNAP", "REACT", "DEEP"] = "REACT"
    is_report: bool = False      # True if response is a full institutional research report

    # --- Phase 1: portfolio output fields (all optional) ---
    market_context: Optional[list[MarketContextCard]] = None
    allocation_breakdown: Optional[list[AllocationSegment]] = None
    portfolio_stocks: Optional[list[PortfolioStockCard]] = None
    scenario_analysis: Optional[list[ScenarioCard]] = None
    action_prompts: Optional[list[ActionPrompt]] = None
    sebi_disclaimer: Optional[str] = None
    is_portfolio_response: Optional[bool] = None
    profiler_needed: bool | None = None

    # --- Clarification fields ---
    clarification_needed: bool | None = None
    clarification_questions: list[ClarificationQuestion] | None = None
    clarification_context: str | None = None
