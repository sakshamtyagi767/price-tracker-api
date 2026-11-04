from app.services.scraper import (
    scraper_service,
    ScraperService,
    ScrapedProduct,
    normalize_url,
)
from app.services.alert_service import alert_service, AlertService

__all__ = [
    "scraper_service",
    "ScraperService",
    "ScrapedProduct",
    "normalize_url",
    "alert_service",
    "AlertService",
]
