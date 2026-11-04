import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
from sqlalchemy.orm import Session

from app.models.tracked_item import TrackedItem
from app.models.product import Product

logger = logging.getLogger("price_tracker.alerts")
logging.basicConfig(level=logging.INFO)


class AlertService:
    """Dispatches notifications across multiple channels (Email, Discord, Webhook)."""

    # 24-hour cooldown between duplicate alerts for the same item to prevent alert fatigue
    NOTIFICATION_COOLDOWN_HOURS = 24

    def should_notify(self, item: TrackedItem, current_price: float) -> bool:
        """Determines if an alert should be triggered based on price threshold and cooldown."""
        if not item.is_active:
            return False

        # Alert condition: current price must be at or below target price
        if current_price > item.target_price:
            return False

        # Cooldown check
        if item.last_notified_at:
            cooldown_period = timedelta(hours=self.NOTIFICATION_COOLDOWN_HOURS)
            now = datetime.now(timezone.utc)
            # Ensure timezone-aware comparison
            last_notified = item.last_notified_at
            if last_notified.tzinfo is None:
                last_notified = last_notified.replace(tzinfo=timezone.utc)
            if (now - last_notified) < cooldown_period:
                logger.info(
                    f"Item {item.id} alert skipped: in cooldown period (last notified: {item.last_notified_at})"
                )
                return False

        return True

    def dispatch_alert(self, item: TrackedItem, product: Product, db: Session) -> bool:
        """Sends an alert through the configured channel and updates the timestamp."""
        channel = item.notification_channel.upper()
        destination = item.notification_destination or item.user.email
        price = product.current_price

        success = False
        message = (
            f"🚨 PRICE DROP ALERT: '{product.title}' has dropped to {product.currency} {price:.2f}! "
            f"Your target was {product.currency} {item.target_price:.2f}. Link: {product.url}"
        )

        try:
            if channel == "DISCORD" and destination and destination.startswith("http"):
                success = self._send_discord_webhook(destination, product, item)
            elif channel == "WEBHOOK" and destination and destination.startswith("http"):
                success = self._send_generic_webhook(destination, product, item)
            else:
                # Default / EMAIL channel
                success = self._send_email(destination, product, item, message)

            if success:
                item.last_notified_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Alert sent successfully to {destination} via {channel}")
        except Exception as e:
            logger.error(f"Failed to dispatch alert for item {item.id} via {channel}: {e}")

        return success

    def _send_email(self, recipient: str, product: Product, item: TrackedItem, body: str) -> bool:
        """Simulates or dispatches an email notification."""
        # In development / sandbox, log email content cleanly
        logger.info(f"📧 [EMAIL DISPATCHED] To: {recipient} | Subject: Price Drop Alert for {product.title}")
        logger.info(f"Content: {body}")
        return True

    def _send_discord_webhook(self, webhook_url: str, product: Product, item: TrackedItem) -> bool:
        """Sends an embedded notification directly to a Discord channel via webhook."""
        embed = {
            "title": f"🚨 Price Drop: {product.title}",
            "url": product.url,
            "color": 3066993,  # Green
            "fields": [
                {"name": "Current Price", "value": f"${product.current_price:.2f}", "inline": True},
                {"name": "Target Price", "value": f"${item.target_price:.2f}", "inline": True},
                {"name": "Savings", "value": f"${(item.target_price - (product.current_price or 0)):.2f}", "inline": True},
            ],
            "footer": {"text": "Price Tracker Alert System"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if product.image_url:
            embed["thumbnail"] = {"url": product.image_url}

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook_url, json={"embeds": [embed]})
            return resp.status_code in (200, 204)

    def _send_generic_webhook(self, webhook_url: str, product: Product, item: TrackedItem) -> bool:
        """Sends a JSON event payload to a custom user webhook endpoint."""
        payload = {
            "event": "price_drop_alert",
            "tracked_item_id": item.id,
            "product_id": product.id,
            "product_title": product.title,
            "product_url": product.url,
            "current_price": product.current_price,
            "target_price": item.target_price,
            "currency": product.currency,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook_url, json=payload)
            return resp.is_success


alert_service = AlertService()
