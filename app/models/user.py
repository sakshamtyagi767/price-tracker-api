import enum
from typing import List, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tracked_item import TrackedItem


class UserTier(str, enum.Enum):
    FREE = "FREE"
    PREMIUM = "PREMIUM"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[UserTier] = mapped_column(
        Enum(UserTier), default=UserTier.FREE, nullable=False
    )
    quota_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # One User can have many TrackedItems
    tracked_items: Mapped[List["TrackedItem"]] = relationship(
        "TrackedItem", back_populates="user", cascade="all, delete-orphan"
    )
