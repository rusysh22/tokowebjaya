from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery = Celery(
    "tokowebjaya",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.billing",
        "app.tasks.invoice",
    ],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Periodic tasks (beat schedule)
celery.conf.beat_schedule = {
    # Run billing check every day at 07:00 WIB
    "process-due-subscriptions": {
        "task": "app.tasks.billing.process_due_subscriptions",
        "schedule": crontab(hour=0, minute=0),  # midnight UTC = 07:00 WIB
    },
    # Retry past_due subscriptions every 3 days
    "retry-past-due-subscriptions": {
        "task": "app.tasks.billing.retry_past_due_subscriptions",
        "schedule": crontab(hour=1, minute=0, day_of_week="1,4"),  # Mon & Thu 01:00 UTC
    },
    # Mark overdue invoices daily
    "mark-overdue-invoices": {
        "task": "app.tasks.billing.mark_overdue_invoices",
        "schedule": crontab(hour=0, minute=30),
    },
}
