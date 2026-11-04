from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class PriceDataPoint(BaseModel):
    price: float
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductAnalyticsResponse(BaseModel):
    product_id: int
    title: str
    currency: str
    current_price: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]
    average_price: Optional[float]
    all_time_low: bool
    price_change_amount: Optional[float]
    price_change_percentage: Optional[float]
    labels: List[str]  # ISO timestamp strings formatted for Chart.js / ApexCharts
    prices: List[float]  # Corresponding prices for the line chart
    history: List[PriceDataPoint]
