"""Watchlist request/response schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

Market = Literal["US", "IN"]


class WatchlistItem(BaseModel):
    id: str
    ticker: str
    market: Market
    note: str | None = None
    created_at: datetime


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    market: Market
    note: str | None = Field(default=None, max_length=500)


class WatchlistListResponse(BaseModel):
    items: list[WatchlistItem]
    count: int
