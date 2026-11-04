from typing import Annotated, Any, cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.product import Product
from app.models.price_history import PriceHistory
from app.schemas.analytics import ProductAnalyticsResponse, PriceDataPoint
from app.workers.tasks import poll_all_products_task

router = APIRouter(prefix="/analytics", tags=["Analytics & Time-Series"])


@router.get("/products/{product_id}/history", response_model=ProductAnalyticsResponse)
def get_product_price_analytics(
    product_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Time-series price history analytics formatted for charting libraries (Chart.js / Recharts).
    Calculates all-time low, high, average, and price drop percentage.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found."
        )

    # Fetch time-series snapshots in chronological order
    history_records = (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.recorded_at.asc())
        .all()
    )

    if not history_records:
        # Fallback if product was created but no history records yet
        current = product.current_price or 0.0
        return ProductAnalyticsResponse(
            product_id=product.id,
            title=product.title or "Unknown Product",
            currency=product.currency,
            current_price=product.current_price,
            min_price=current,
            max_price=current,
            average_price=current,
            all_time_low=True,
            price_change_amount=0.0,
            price_change_percentage=0.0,
            labels=[],
            prices=[],
            history=[],
        )

    prices_list = [record.price for record in history_records]
    labels_list = [record.recorded_at.isoformat() for record in history_records]
    
    min_p = min(prices_list)
    max_p = max(prices_list)
    avg_p = sum(prices_list) / len(prices_list)
    current_p = product.current_price if product.current_price is not None else prices_list[-1]
    
    first_p = prices_list[0]
    change_amount = round(current_p - first_p, 2)
    change_pct = round(((current_p - first_p) / first_p) * 100, 2) if first_p > 0 else 0.0
    all_time_low = (current_p <= min_p)

    return ProductAnalyticsResponse(
        product_id=product.id,
        title=product.title or "Unknown Product",
        currency=product.currency,
        current_price=current_p,
        min_price=min_p,
        max_price=max_p,
        average_price=round(avg_p, 2),
        all_time_low=all_time_low,
        price_change_amount=change_amount,
        price_change_percentage=change_pct,
        labels=labels_list,
        prices=prices_list,
        history=[
            PriceDataPoint(price=r.price, recorded_at=r.recorded_at)
            for r in history_records
        ],
    )


@router.post("/trigger-poll", status_code=status.HTTP_202_ACCEPTED)
def trigger_background_poll(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Manual trigger to execute the background polling task.
    Enables immediate testing of background workers without waiting for 6-hour cron.
    """
    # For local testing without active Redis, Celery allows calling task directly
    try:
        task_caller = cast(Any, poll_all_products_task)
        res = task_caller.delay()
        return {"status": "enqueued", "task_id": str(res.id)}
    except Exception as e:
        # Fallback to synchronous run if Redis broker is not currently running locally
        result = poll_all_products_task()
        return {"status": "executed_synchronously", "details": result}
