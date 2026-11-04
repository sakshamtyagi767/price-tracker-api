from datetime import datetime, timezone
from typing import Annotated, List
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.product import Product
from app.models.tracked_item import TrackedItem
from app.models.price_history import PriceHistory
from app.schemas.tracked_item import (
    TrackedItemCreate,
    TrackedItemUpdate,
    TrackedItemResponse,
)
from app.services.scraper import scraper_service, normalize_url

router = APIRouter(prefix="/tracked-items", tags=["Tracked Items"])


@router.post("", response_model=TrackedItemResponse, status_code=status.HTTP_201_CREATED)
def create_tracked_item(
    item_in: TrackedItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Tracks a new product URL for the authenticated user.
    Enforces user tier quotas, normalizes the URL to deduplicate products across users,
    and scrapes the product data immediately upon first ingestion.
    """
    # 1. Enforce Tier Quotas
    current_count = (
        db.query(TrackedItem)
        .filter(TrackedItem.user_id == current_user.id, TrackedItem.is_active == True)
        .count()
    )
    if current_count >= current_user.quota_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Quota exceeded. Your '{current_user.tier}' tier allows tracking up to "
                f"{current_user.quota_limit} active items. Upgrade to PREMIUM to track up to 50 items."
            ),
        )

    # 2. Normalize URL to avoid duplicates with different query tracking parameters
    normalized_url = normalize_url(item_in.url)
    domain = urlparse(normalized_url).netloc.lower()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL format. Please provide a valid HTTP/HTTPS e-commerce link."
        )

    # 3. Check if Product already exists in canonical catalog (Deduplication)
    product = db.query(Product).filter(Product.url == normalized_url).first()

    if not product:
        # Scrape product metadata immediately on first ingestion
        try:
            scraped_data = scraper_service.scrape(normalized_url)
            product = Product(
                url=normalized_url,
                domain=domain,
                title=scraped_data.title,
                image_url=scraped_data.image_url,
                current_price=scraped_data.price,
                currency=scraped_data.currency,
                last_scraped_at=datetime.now(timezone.utc),
            )
            db.add(product)
            db.flush()  # Generate product.id

            # Save initial price snapshot into PriceHistory
            initial_history = PriceHistory(
                product_id=product.id,
                price=scraped_data.price,
                recorded_at=datetime.now(timezone.utc),
            )
            db.add(initial_history)
        except Exception as e:
            # If live scraping fails (e.g. network/anti-bot during test), create product skeleton
            product = Product(
                url=normalized_url,
                domain=domain,
                title="Pending Price Fetch",
                image_url=None,
                current_price=None,
                currency="USD",
                last_scraped_at=None,
            )
            db.add(product)
            db.flush()

    # 4. Check if this user is already tracking this product
    existing_track = (
        db.query(TrackedItem)
        .filter(
            TrackedItem.user_id == current_user.id,
            TrackedItem.product_id == product.id,
        )
        .first()
    )
    if existing_track:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already tracking this product. Use PATCH to update your target price.",
        )

    # 5. Create multi-tenant tracking link
    tracked_item = TrackedItem(
        user_id=current_user.id,
        product_id=product.id,
        target_price=item_in.target_price,
        notification_channel=item_in.notification_channel.upper(),
        notification_destination=item_in.notification_destination,
        is_active=True,
    )
    db.add(tracked_item)
    db.commit()
    db.refresh(tracked_item)
    return tracked_item


@router.get("", response_model=List[TrackedItemResponse])
def get_user_tracked_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retrieve all tracked products for the current authenticated user."""
    items = (
        db.query(TrackedItem)
        .options(joinedload(TrackedItem.product))
        .filter(TrackedItem.user_id == current_user.id)
        .all()
    )
    return items


@router.get("/{item_id}", response_model=TrackedItemResponse)
def get_tracked_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retrieve a single tracked item by ID (enforcing user ownership)."""
    item = (
        db.query(TrackedItem)
        .options(joinedload(TrackedItem.product))
        .filter(TrackedItem.id == item_id, TrackedItem.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked item not found.")
    return item


@router.patch("/{item_id}", response_model=TrackedItemResponse)
def update_tracked_item(
    item_id: int,
    item_update: TrackedItemUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update target price, active status, or notification destination for a tracked item."""
    item = (
        db.query(TrackedItem)
        .options(joinedload(TrackedItem.product))
        .filter(TrackedItem.id == item_id, TrackedItem.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked item not found.")

    if item_update.target_price is not None:
        item.target_price = item_update.target_price
    if item_update.notification_channel is not None:
        item.notification_channel = item_update.notification_channel.upper()
    if item_update.notification_destination is not None:
        item.notification_destination = item_update.notification_destination
    if item_update.is_active is not None:
        item.is_active = item_update.is_active

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tracked_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Remove a product from the user's tracking watchlist."""
    item = (
        db.query(TrackedItem)
        .filter(TrackedItem.id == item_id, TrackedItem.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked item not found.")

    db.delete(item)
    db.commit()
    return None
