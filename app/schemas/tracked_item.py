from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ProductResponse(BaseModel):
    id: int
    url: str
    domain: str
    title: Optional[str] = None
    image_url: Optional[str] = None
    current_price: Optional[float] = None
    currency: str
    last_scraped_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TrackedItemCreate(BaseModel):
    url: str = Field(description="The e-commerce product URL to track")
    target_price: float = Field(
        gt=0, description="Target price threshold that triggers an alert"
    )
    notification_channel: str = Field(
        default="EMAIL", description="EMAIL, DISCORD, or WEBHOOK"
    )
    notification_destination: Optional[str] = Field(
        default=None,
        description="Optional custom destination (e.g. Discord webhook URL)",
    )


class TrackedItemUpdate(BaseModel):
    target_price: Optional[float] = Field(
        default=None, gt=0, description="New target price"
    )
    notification_channel: Optional[str] = Field(
        default=None, description="EMAIL, DISCORD, or WEBHOOK"
    )
    notification_destination: Optional[str] = Field(
        default=None, description="Custom webhook URL"
    )
    is_active: Optional[bool] = Field(
        default=None, description="Pause or resume tracking"
    )


class TrackedItemResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    target_price: float
    notification_channel: str
    notification_destination: Optional[str] = None
    is_active: bool
    last_notified_at: Optional[datetime] = None
    created_at: datetime
    product: ProductResponse

    model_config = ConfigDict(from_attributes=True)
