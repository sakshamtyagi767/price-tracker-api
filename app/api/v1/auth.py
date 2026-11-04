from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.api.deps import get_current_user
from app.models.user import User, UserTier
from app.schemas.user import UserCreate, UserResponse
from app.schemas.token import Token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(user_in: UserCreate, db: Annotated[Session, Depends(get_db)]):
    """Register a new user account with tier quotas."""
    # 1. Check if user already exists
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    # 2. Determine quota limit based on subscription tier
    quota_limit = 50 if user_in.tier == UserTier.PREMIUM else 5

    # 3. Create user record with hashed password
    new_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        tier=user_in.tier,
        quota_limit=quota_limit,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    """OAuth2 compatible token login, get an access token for future requests."""
    # Find user by email (form_data.username contains the email)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    # Generate JWT token with user ID as subject
    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: Annotated[User, Depends(get_current_user)]):
    """Retrieve the current logged-in user profile."""
    return current_user
