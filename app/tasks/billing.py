"""
Recurring billing automation tasks.

Flow:
1. process_due_subscriptions — runs daily, finds subscriptions with next_billing_date <= now,
   creates a new order and attempts charge via Duitku. On success → create invoice, update
   next_billing_date. On failure → mark subscription as past_due, send notification.

2. retry_past_due_subscriptions — runs twice weekly, retries past_due subscriptions once more.
   After MAX_RETRIES failures → expire subscription.

3. mark_overdue_invoices — runs daily, moves unpaid invoices past due_date to overdue.
"""

import uuid
import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.subscription import Subscription, SubscriptionStatus, BillingCycle
from app.models.order import Order, OrderStatus, OrderType, PaymentGateway
from app.models.invoice import Invoice, InvoiceStatus
from app.models.product import Product
from app.services.payment import generate_order_number

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3


@celery.task(name="app.tasks.billing.process_due_subscriptions", bind=True)
def process_due_subscriptions(self):
    """Find all active subscriptions due today and charge them."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due_subs = (
            db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.active,
                Subscription.next_billing_date <= now,
            )
            .all()
        )

        logger.info(f"[billing] Found {len(due_subs)} due subscriptions")

        for sub in due_subs:
            charge_subscription.delay(str(sub.id))

    finally:
        db.close()


@celery.task(name="app.tasks.billing.retry_past_due_subscriptions", bind=True)
def retry_past_due_subscriptions(self):
    """Retry charging past_due subscriptions."""
    db = SessionLocal()
    try:
        past_due = (
            db.query(Subscription)
            .filter(Subscription.status == SubscriptionStatus.past_due)
            .all()
        )

        logger.info(f"[billing] Retrying {len(past_due)} past_due subscriptions")

        for sub in past_due:
            # Count failed orders for this sub in the last 30 days
            since = datetime.utcnow() - timedelta(days=30)
            fail_count = (
                db.query(Order)
                .filter(
                    Order.user_id == sub.user_id,
                    Order.product_id == sub.product_id,
                    Order.type == OrderType.subscription,
                    Order.status == OrderStatus.failed,
                    Order.created_at >= since,
                )
                .count()
            )

            if fail_count >= MAX_RETRY_ATTEMPTS:
                sub.status = SubscriptionStatus.expired
                sub.expires_at = datetime.utcnow()
                db.commit()
                _send_subscription_expired_email(sub, db)
                logger.info(f"[billing] Subscription {sub.id} expired after {fail_count} failures")
            else:
                charge_subscription.delay(str(sub.id))

    finally:
        db.close()


@celery.task(
    name="app.tasks.billing.charge_subscription",
    bind=True,
    max_retries=2,
    default_retry_delay=3600,  # retry after 1 hour on Celery-level error
)
def charge_subscription(self, subscription_id: str):
    """
    Attempt to charge a single subscription.
    Creates a renewal Order and calls the payment gateway synchronously
    (for card-on-file / tokenized payments). Falls back to sending a
    payment-link email if no stored token exists.
    """
    import asyncio
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            return

        if sub.status not in (SubscriptionStatus.active, SubscriptionStatus.past_due):
            return

        product = db.query(Product).filter(Product.id == sub.product_id).first()
        if not product:
            return

        amount = (
            float(product.price_monthly)
            if sub.billing_cycle == BillingCycle.monthly
            else float(product.price_yearly)
        )

        order = Order(
            id=uuid.uuid4(),
            order_number=generate_order_number(),
            user_id=sub.user_id,
            product_id=sub.product_id,
            type=OrderType.subscription,
            amount=amount,
            status=OrderStatus.pending,
            payment_gateway=PaymentGateway.duitku,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # Attempt charge via payment gateway
        # NOTE: In production, use stored payment token (card-on-file).
        # Here we create a payment link and email it to the customer.
        try:
            from app.services.payment import duitku
            return_url = f"{settings.BASE_URL}/id/checkout/return/{order.id}"
            result = asyncio.get_event_loop().run_until_complete(
                duitku.create_payment(
                    order_number=order.order_number,
                    amount=int(amount),
                    product_name=product.name_id,
                    customer_name=sub.user.name if sub.user else "Customer",
                    customer_email=sub.user.email if sub.user else "",
                    return_url=return_url,
                )
            )
            payment_url = result.get("paymentUrl", "")
            order.gateway_reference = result.get("reference", "")
            order.gateway_payment_url = payment_url
            db.commit()

            # Send renewal payment link email
            _send_renewal_email(sub, order, payment_url, db)

            logger.info(f"[billing] Payment link sent for subscription {sub.id}, order {order.order_number}")

        except Exception as e:
            # Payment gateway error → mark order failed, subscription past_due
            order.status = OrderStatus.failed
            sub.status = SubscriptionStatus.past_due
            db.commit()
            logger.error(f"[billing] Charge failed for subscription {sub.id}: {e}")
            _send_payment_failed_email(sub, order, db)
            return

    except Exception as exc:
        logger.error(f"[billing] Unexpected error charging subscription {subscription_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            pass
    finally:
        db.close()


@celery.task(name="app.tasks.billing.confirm_subscription_renewal")
def confirm_subscription_renewal(order_id: str):
    """
    Called when a renewal payment is confirmed (via webhook).
    Updates subscription billing dates and creates invoice.
    """
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order or order.status != OrderStatus.paid:
            return

        # Find the related subscription
        sub = (
            db.query(Subscription)
            .filter(
                Subscription.user_id == order.user_id,
                Subscription.product_id == order.product_id,
                Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.past_due]),
            )
            .order_by(Subscription.created_at.desc())
            .first()
        )

        if not sub:
            return

        # Advance next billing date
        if sub.billing_cycle == BillingCycle.monthly:
            sub.next_billing_date = sub.next_billing_date + timedelta(days=30)
        else:
            sub.next_billing_date = sub.next_billing_date + timedelta(days=365)

        sub.status = SubscriptionStatus.active
        db.commit()

        # Create invoice for this renewal
        from app.tasks.invoice import create_invoice_task
        create_invoice_task.delay(str(order.id))

        logger.info(f"[billing] Subscription {sub.id} renewed, next billing: {sub.next_billing_date}")

    finally:
        db.close()


@celery.task(name="app.tasks.billing.mark_overdue_invoices")
def mark_overdue_invoices():
    """Mark all unpaid invoices past their due_date as overdue."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        updated = (
            db.query(Invoice)
            .filter(
                Invoice.status == InvoiceStatus.unpaid,
                Invoice.due_date < now,
            )
            .update({"status": InvoiceStatus.overdue}, synchronize_session=False)
        )
        db.commit()
        logger.info(f"[billing] Marked {updated} invoices as overdue")
    finally:
        db.close()


# ─── Email helpers ────────────────────────────────────────────────────────────

def _send_renewal_email(sub: Subscription, order: Order, payment_url: str, db):
    """Send renewal payment link email to customer."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    if not settings.SMTP_USER or not sub.user:
        return

    product_name = sub.product.name_id if sub.product else "Produk"
    amount_fmt = f"Rp {float(order.amount):,.0f}"

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = sub.user.email
    msg["Subject"] = f"Perpanjang Langganan — {product_name}"

    body = f"""Hai {sub.user.name},

Langganan Anda untuk {product_name} akan diperpanjang.

Order: {order.order_number}
Tagihan: {amount_fmt}

Silakan selesaikan pembayaran melalui tautan berikut:
{payment_url}

Tautan ini berlaku selama 24 jam.

Salam,
Tim Toko Web Jaya
"""
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        logger.error(f"[billing] Failed to send renewal email: {e}")


def _send_payment_failed_email(sub: Subscription, order: Order, db):
    """Notify customer their renewal payment failed."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    if not settings.SMTP_USER or not sub.user:
        return

    product_name = sub.product.name_id if sub.product else "Produk"

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = sub.user.email
    msg["Subject"] = f"Pembayaran Gagal — {product_name}"

    body = f"""Hai {sub.user.name},

Pembayaran perpanjangan langganan {product_name} Anda gagal diproses.

Kami akan mencoba kembali dalam beberapa hari ke depan. Pastikan metode pembayaran Anda aktif.

Jika ada pertanyaan, hubungi kami di contact@tokowebjaya.com.

Salam,
Tim Toko Web Jaya
"""
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        logger.error(f"[billing] Failed to send payment failed email: {e}")


def _send_subscription_expired_email(sub: Subscription, db):
    """Notify customer their subscription has expired."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    if not settings.SMTP_USER or not sub.user:
        return

    product_name = sub.product.name_id if sub.product else "Produk"

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = sub.user.email
    msg["Subject"] = f"Langganan Berakhir — {product_name}"

    body = f"""Hai {sub.user.name},

Langganan Anda untuk {product_name} telah berakhir setelah beberapa kali percobaan pembayaran gagal.

Untuk mengaktifkan kembali, silakan kunjungi:
{settings.BASE_URL}/id/catalog

Salam,
Tim Toko Web Jaya
"""
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        logger.error(f"[billing] Failed to send expired email: {e}")
