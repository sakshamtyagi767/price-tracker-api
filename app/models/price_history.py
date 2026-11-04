from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (Index("ix_product_recorded_at", "product_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationship
    product: Mapped["Product"] = relationship("Product", back_populates="price_history")
