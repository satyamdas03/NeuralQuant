"""Alert subscription request/response schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

Market = Literal["US", "IN"]
AlertType = Literal["score_change", "regime_change", "threshold"]


class AlertSubscriptionCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    market: Market = "US"
    alert_type: AlertType = "score_change"
    threshold: Optional[float] = Field(default=None, ge=0, le=1, description="For threshold alerts: trigger when score crosses this")
    min_delta: float = Field(default=0.10, ge=0.01, le=0.50, description="Minimum score change to trigger alert")


class AlertSubscription(BaseModel):
    id: str
    ticker: str
    market: Market
    alert_type: AlertType
    threshold: Optional[float] = None
    min_delta: float
    last_triggered_at: Optional[datetime] = None
    created_at: datetime


class AlertSubscriptionListResponse(BaseModel):
    items: list[AlertSubscription]
    count: int


class AlertDelivery(BaseModel):
    id: str
    ticker: str
    market: Market
    alert_type: AlertType
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    delivered_at: datetime


class AlertDeliveryListResponse(BaseModel):
    items: list[AlertDelivery]
    count: int