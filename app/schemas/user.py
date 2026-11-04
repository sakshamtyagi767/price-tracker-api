from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.user import UserTier


# Shared properties
class UserBase(BaseModel):
    email: EmailStr


# Schema for User Registration (Input)
class UserCreate(UserBase):
    password: str = Field(
        min_length=8, description="Password must be at least 8 characters"
    )
    tier: UserTier = UserTier.FREE


# Schema for Returning User Data (Output - NO PASSWORD EXPOSED!)
class UserResponse(UserBase):
    id: int
    tier: UserTier
    quota_limit: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
