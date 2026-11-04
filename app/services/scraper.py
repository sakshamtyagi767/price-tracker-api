import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlparse, urlunparse
import httpx
from bs4 import BeautifulSoup


@dataclass
class ScrapedProduct:
    title: str
    price: float
    currency: str
    image_url: Optional[str]
    domain: str


def clean_price(price_str: str) -> float:
    """Extracts a numeric float from global price formats like '$1,299.99', '€ 45,50', '₹49,999'."""
    match = re.search(r"[\d,.]+", price_str)
    if not match:
        raise ValueError(f"Could not extract numeric price from: {price_str}")

    cleaned = match.group(0)

    # 1. Both comma and dot present
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") < cleaned.rfind("."):
            # US/UK style: 1,299.99
            cleaned = cleaned.replace(",", "")
        else:
            # European style: 1.299,99
            cleaned = cleaned.replace(".", "").replace(",", ".")

    # 2. Only comma present
    elif "," in cleaned:
        parts = cleaned.split(",")
        # If exactly 2 decimal digits at end (e.g., 45,50), it is a European decimal
        if len(parts[-1]) == 2 and len(parts) == 2:
            cleaned = cleaned.replace(",", ".")
        else:
            # Thousands separator (e.g., 49,999 or 1,000,000)
            cleaned = cleaned.replace(",", "")

    return float(cleaned)


def normalize_url(raw_url: str) -> str:
    """Removes query tracking parameters (?ref=..., ?tag=...) for clean deduplication."""
    parsed = urlparse(raw_url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


class BaseScraper(ABC):
    """Abstract Strategy Interface."""

    @abstractmethod
    def can_handle(self, domain: str) -> bool:
        """Returns True if this scraper knows how to parse this domain."""
        pass

    @abstractmethod
    def parse(self, soup: BeautifulSoup, url: str) -> ScrapedProduct:
        """Parses HTML BeautifulSoup object and returns ScrapedProduct."""
        pass


class AmazonScraper(BaseScraper):
    """Scraper specialized for Amazon domains."""

    def can_handle(self, domain: str) -> bool:
        return "amazon." in domain

    def parse(self, soup: BeautifulSoup, url: str) -> ScrapedProduct:
        domain = urlparse(url).netloc

        # Title
        title_el = soup.select_one("#productTitle")
        title = title_el.get_text(strip=True) if title_el else "Unknown Amazon Product"

        # Price (Amazon puts full price in .a-offscreen)
        price_el = (
            soup.select_one(".a-price .a-offscreen")
            or soup.select_one("#priceblock_ourprice")
            or soup.select_one("#priceblock_dealprice")
        )
        if not price_el:
            raise ValueError("Could not find price on Amazon page")
        price = clean_price(price_el.get_text(strip=True))

        # Image
        img_el = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront")
        image_url = img_el.get("src") if img_el else None
        if isinstance(image_url, list):
            image_url = image_url[0]

        return ScrapedProduct(
            title=title,
            price=price,
            currency="USD",
            image_url=image_url,
            domain=domain,
        )


class GenericScraper(BaseScraper):
    """Fallback scraper using OpenGraph / Schema.org meta tags."""

    def can_handle(self, domain: str) -> bool:
        return True  # Catch-all fallback

    def parse(self, soup: BeautifulSoup, url: str) -> ScrapedProduct:
        domain = urlparse(url).netloc

        # Try OpenGraph title, then <title>
        og_title = soup.find("meta", property="og:title")
        title = (
            og_title.get("content")
            if og_title
            else (soup.title.string if soup.title else "Unknown Product")
        )

        # Try OpenGraph image
        og_image = soup.find("meta", property="og:image")
        image_url = og_image.get("content") if og_image else None

        # Try OpenGraph price or common price selectors
        og_price = soup.find("meta", property="og:price:amount") or soup.find(
            "meta", property="product:price:amount"
        )
        if og_price and og_price.get("content"):
            price = clean_price(str(og_price.get("content")))
        else:
            # Fallback heuristic: find first element with a price-like currency sign
            price_candidate = soup.find(string=re.compile(r"[\$\£\€]\s*\d+"))
            if not price_candidate:
                raise ValueError("Could not find product price on page")
            price = clean_price(str(price_candidate))

        return ScrapedProduct(
            title=str(title).strip(),
            price=price,
            currency="USD",
            image_url=str(image_url) if image_url else None,
            domain=domain,
        )


class ScraperService:
    """Orchestrates HTTP fetching and scraper strategy selection."""

    USER_AGENTS = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    def __init__(self, scrapers: Optional[List[BaseScraper]] = None):
        self.scrapers: List[BaseScraper] = scrapers or [
            AmazonScraper(),
            GenericScraper(),  # Always last as fallback
        ]

    def get_scraper_for_url(self, url: str) -> BaseScraper:
        domain = urlparse(url).netloc.lower()
        for scraper in self.scrapers:
            if scraper.can_handle(domain):
                return scraper
        return GenericScraper()

    def scrape(self, raw_url: str) -> ScrapedProduct:
        url = normalize_url(raw_url)
        scraper = self.get_scraper_for_url(url)

        headers = {
            "User-Agent": self.USER_AGENTS,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

        # Follow redirects, set timeout to 10 seconds
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code != 200:
                raise ValueError(
                    f"Failed to fetch page. HTTP status code: {response.status_code}"
                )

            soup = BeautifulSoup(response.text, "html.parser")
            return scraper.parse(soup, url)


# Singleton instance
scraper_service = ScraperService()
