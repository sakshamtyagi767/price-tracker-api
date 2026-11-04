import logging
from typing import Any, cast
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.product import Product
from app.models.tracked_item import TrackedItem
from app.models.price_history import PriceHistory
from app.services.scraper import scraper_service
from app.services.alert_service import alert_service

logger = logging.getLogger("price_tracker.tasks")


@celery_app.task(name="app.workers.tasks.scrape_single_product_task", bind=True, max_retries=3, default_retry_delay=60)
def scrape_single_product_task(self: Any, product_id: int):
    """
    Background job to scrape an individual product, log the new price into
    the time-series PriceHistory table, and trigger alerts if prices dropped.
    """
    db = SessionLocal()
    try:
        product = (
            db.query(Product)
            .options(joinedload(Product.tracked_items).joinedload(TrackedItem.user))
            .filter(Product.id == product_id)
            .first()
        )
        if not product:
            logger.warning(f"Product {product_id} not found. Skipping.")
            return

        logger.info(f"Scraping product {product.id}: {product.url}")
        scraped = scraper_service.scrape(product.url)

        # 1. Update Product metadata and latest price
        old_price = product.current_price
        product.current_price = scraped.price
        product.last_scraped_at = datetime.now(timezone.utc)
        if scraped.title and product.title == "Pending Price Fetch":
            product.title = scraped.title
        if scraped.image_url and not product.image_url:
            product.image_url = scraped.image_url

        # 2. Record historical snapshot in PriceHistory table
        history = PriceHistory(
            product_id=product.id,
            price=scraped.price,
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(history)
        db.commit()

        logger.info(
            f"Product {product.id} price updated: {old_price} -> {scraped.price}"
        )

        # 3. Event-Driven Alert Check: Evaluate all active users tracking this product
        for item in product.tracked_items:
            if alert_service.should_notify(item, scraped.price):
                alert_service.dispatch_alert(item, product, db)

        return {"product_id": product.id, "new_price": scraped.price}

    except Exception as exc:
        logger.error(f"Error scraping product {product_id}: {exc}")
        db.rollback()
        # Retry with exponential backoff if transient network failure
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.poll_all_products_task")
def poll_all_products_task():
    """
    Periodic orchestrator task. Finds all distinct active products
    and queues asynchronous scrape jobs for each one.
    """
    db = SessionLocal()
    try:
        active_products = (
            db.query(Product.id)
            .join(TrackedItem, TrackedItem.product_id == Product.id)
            .filter(TrackedItem.is_active == True)
            .distinct()
            .all()
        )

        logger.info(f"Starting scheduled polling for {len(active_products)} active products.")

        enqueued_count = 0
        task_caller = cast(Any, scrape_single_product_task)
        for (prod_id,) in active_products:
            task_caller.delay(prod_id)
            enqueued_count += 1

        return {"enqueued_tasks": enqueued_count}
    finally:
        db.close()
