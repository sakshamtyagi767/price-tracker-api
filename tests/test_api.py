from datetime import datetime, timezone, timedelta
from app.models.user import User, UserTier
from app.models.product import Product
from app.models.tracked_item import TrackedItem
from app.models.price_history import PriceHistory
from app.services.alert_service import alert_service


def get_auth_token(client, email="user@example.com", password="password123", tier="FREE"):
    """Helper to register and login a user, returning the JWT authorization header."""
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "tier": tier},
    )
    res = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_auth_workflow(client):
    """Verifies registration, duplicate email rejection, and login JWT generation."""
    # 1. Register
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "securepassword", "tier": "FREE"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "alice@example.com"
    assert data["quota_limit"] == 5
    assert "hashed_password" not in data

    # 2. Duplicate rejection
    res_dup = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "securepassword", "tier": "FREE"},
    )
    assert res_dup.status_code == 400

    # 3. Login
    res_login = client.post(
        "/api/v1/auth/login",
        data={"username": "alice@example.com", "password": "securepassword"},
    )
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()


def test_product_deduplication(client, db_session):
    """
    Architectural Test: When two distinct users track the exact same product URL
    (even with different query parameters), the system must only create ONE Product row.
    """
    auth1 = get_auth_token(client, email="user1@example.com")
    auth2 = get_auth_token(client, email="user2@example.com")

    # User 1 tracks product with tracking query parameters
    url1 = "https://www.example.com/product/123?utm_source=google&tag=referral1"
    res1 = client.post(
        "/api/v1/tracked-items",
        json={"url": url1, "target_price": 50.0, "notification_channel": "EMAIL"},
        headers=auth1,
    )
    assert res1.status_code == 201

    # User 2 tracks the same product with different tracking query parameters
    url2 = "https://www.example.com/product/123?ref=newsletter&aff=bob"
    res2 = client.post(
        "/api/v1/tracked-items",
        json={"url": url2, "target_price": 45.0, "notification_channel": "EMAIL"},
        headers=auth2,
    )
    assert res2.status_code == 201

    # Verify Database Catalog has only ONE unique Product record
    products = db_session.query(Product).all()
    assert len(products) == 1
    assert products[0].url == "https://www.example.com/product/123"

    # Verify both users have distinct TrackedItem links
    tracked = db_session.query(TrackedItem).all()
    assert len(tracked) == 2


def test_quota_enforcement(client, db_session):
    """Verifies that users on the FREE tier cannot exceed their 5-item tracking limit."""
    auth = get_auth_token(client, email="freetier@example.com", tier="FREE")

    # Add 5 products (maximum limit for FREE)
    for i in range(5):
        res = client.post(
            "/api/v1/tracked-items",
            json={"url": f"https://www.store.com/item-{i}", "target_price": 100.0},
            headers=auth,
        )
        assert res.status_code == 201

    # Attempt to add the 6th product -> Must be rejected with 403 Forbidden
    res_overflow = client.post(
        "/api/v1/tracked-items",
        json={"url": "https://www.store.com/item-6", "target_price": 100.0},
        headers=auth,
    )
    assert res_overflow.status_code == 403
    assert "Quota exceeded" in res_overflow.json()["detail"]


def test_alert_service_logic(db_session):
    """Verifies alert threshold triggers and 24-hour cooldown logic."""
    user = User(
        email="alert@example.com",
        hashed_password="hash",
        tier=UserTier.FREE,
        quota_limit=5,
    )
    db_session.add(user)
    db_session.flush()

    product = Product(
        url="https://store.com/headphones",
        domain="store.com",
        title="Headphones",
        current_price=250.0,
        currency="USD",
    )
    db_session.add(product)
    db_session.flush()

    item = TrackedItem(
        user_id=user.id,
        product_id=product.id,
        target_price=200.0,
        notification_channel="EMAIL",
    )
    db_session.add(item)
    db_session.commit()

    # 1. Price is $250, target is $200 -> No alert
    assert alert_service.should_notify(item, current_price=250.0) is False

    # 2. Price drops to $199.99 (below target) -> Alert triggers!
    assert alert_service.should_notify(item, current_price=199.99) is True

    # 3. Simulate alert dispatch and verify cooldown
    item.last_notified_at = datetime.now(timezone.utc)
    db_session.commit()

    # Still below target, but within 24-hour cooldown -> Must NOT spam alert
    assert alert_service.should_notify(item, current_price=199.99) is False

    # 4. Fast forward past 24-hour cooldown -> Alert can fire again
    item.last_notified_at = datetime.now(timezone.utc) - timedelta(hours=25)
    db_session.commit()
    assert alert_service.should_notify(item, current_price=199.99) is True


def test_analytics_timeseries(client, db_session):
    """Verifies calculation of min, max, average, and price changes for charts."""
    auth = get_auth_token(client, email="analyst@example.com")

    # Manually seed a product and price snapshots over time
    product = Product(
        url="https://store.com/gpu",
        domain="store.com",
        title="RTX 4080 GPU",
        current_price=999.0,
        currency="USD",
    )
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    prices = [1200.0, 1150.0, 1100.0, 999.0]
    for idx, p in enumerate(prices):
        history = PriceHistory(
            product_id=product.id,
            price=p,
            recorded_at=now - timedelta(days=4 - idx),
        )
        db_session.add(history)
    db_session.commit()

    res = client.get(f"/api/v1/analytics/products/{product.id}/history", headers=auth)
    assert res.status_code == 200
    data = res.json()

    assert data["min_price"] == 999.0
    assert data["max_price"] == 1200.0
    assert data["all_time_low"] is True
    assert data["price_change_amount"] == -201.0  # 999 - 1200
    assert len(data["prices"]) == 4
    assert len(data["labels"]) == 4
