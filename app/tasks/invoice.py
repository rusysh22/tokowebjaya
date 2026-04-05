"""
Celery task: invoice generation.
Retries up to 3 times with 60-second delay on failure.
"""
import logging

from app.services.invoice import create_invoice
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.invoice.create_invoice_task", bind=True, max_retries=3)
def create_invoice_task(self, order_id: str):
    """Celery task wrapper for invoice creation."""
    try:
        create_invoice(order_id)
    except Exception as exc:
        logger.error(f"[invoice] Failed to create invoice for order {order_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
