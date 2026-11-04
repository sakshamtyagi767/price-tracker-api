from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    Integer,
    Float,
    Boolean,
    DateTime,
    String,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.product import Product


class TrackedItem(Base):
    __tablename__ = "tracked_items"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )

    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    notification_channel: Mapped[str] = mapped_column(String(50), default="EMAIL")
    notification_destination: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tracked_items")
    product: Mapped["Product"] = relationship("Product", back_populates="tracked_items")
