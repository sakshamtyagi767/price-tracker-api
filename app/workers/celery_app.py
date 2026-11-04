from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "price_tracker_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Rate limit task execution to prevent IP blocks
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Celery Beat Scheduled Tasks (Periodic cron jobs)
celery_app.conf.beat_schedule = {
    "poll-prices-every-6-hours": {
        "task": "app.workers.tasks.poll_all_products_task",
        # Runs every 6 hours
        "schedule": crontab(minute="0", hour="*/6"),
    },
}
