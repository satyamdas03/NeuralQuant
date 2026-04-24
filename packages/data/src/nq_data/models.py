from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

class OHLCVBar(BaseModel):
    ticker: str
    market: Literal["US", "IN", "GLOBAL"]
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjusted_close: Optional[float] = None
    delivery_pct: Optional[float] = None  # NSE-specific

class FundamentalSnapshot(BaseModel):
    ticker: str
    market: Literal["US", "IN", "GLOBAL"]
    as_of_date: date
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    fcf_yield: Optional[float] = None
    debt_equity: Optional[float] = None
    piotroski_score: Optional[int] = None
    accruals_ratio: Optional[float] = None
    beneish_m_score: Optional[float] = None

class MacroSnapshot(BaseModel):
    as_of_date: date
    vix: Optional[float] = None
    yield_10y: Optional[float] = None
    yield_2y: Optional[float] = None
    yield_spread_2y10y: Optional[float] = None
    hy_spread_oas: Optional[float] = None
    ism_pmi: Optional[float] = None
    cpi_yoy: Optional[float] = None
    fed_funds_rate: Optional[float] = None
    spx_vs_200ma: Optional[float] = None  # % above/below 200-day MA

class NewsItem(BaseModel):
    ticker: str
    source: str
    headline: str
    published_at: datetime
    sentiment_score: Optional[float] = None  # -1.0 to 1.0
    url: Optional[str] = None

class SocialSentiment(BaseModel):
    ticker: str
    source: Literal["reddit", "stocktwits"]
    bullish_pct: float = 0.0
    mention_count: int = 0
    top_topics: list[str] = Field(default_factory=list)
    fetched_at: datetime
