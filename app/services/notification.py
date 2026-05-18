"""
Notification service — create in-app notifications.
All functions accept a SQLAlchemy Session and are synchronous
so they can be called from both request handlers and Celery tasks.
"""
from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType


def _create(
    db: Session,
    user_id,
    type: NotificationType,
    title: str,
    body: str = None,
    link: str = None,
    *,
    order_id=None,
    subscription_id=None,
    invoice_id=None,
):
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
        order_id=order_id,
        subscription_id=subscription_id,
        invoice_id=invoice_id,
    )
    db.add(notif)
    db.commit()
    return notif


# ─── Order notifications ─────────────────────────────────────────────────────

def notify_order_paid(db: Session, order, locale: str = "id"):
    product_name = ""
    if order.product:
        product_name = order.product.name_id if locale == "id" else order.product.name_en

    if locale == "id":
        title = f"Pembayaran berhasil — {order.order_number}"
        body  = f"Pesanan {product_name} telah dikonfirmasi. Invoice sedang disiapkan."
    else:
        title = f"Payment confirmed — {order.order_number}"
        body  = f"Your order for {product_name} has been confirmed. Invoice is being prepared."

    return _create(
        db, order.user_id,
        NotificationType.order_paid,
        title, body,
        link=f"/{locale}/dashboard/orders/{order.id}",
        order_id=order.id,
    )


def notify_order_failed(db: Session, order, locale: str = "id"):
    if locale == "id":
        title = f"Pembayaran gagal — {order.order_number}"
        body  = "Pembayaran Anda tidak berhasil diproses. Silakan coba lagi."
    else:
        title = f"Payment failed — {order.order_number}"
        body  = "Your payment could not be processed. Please try again."

    return _create(
        db, order.user_id,
        NotificationType.order_failed,
        title, body,
        link=f"/{locale}/dashboard/orders/{order.id}",
        order_id=order.id,
    )


def notify_invoice_created(db: Session, invoice, order, locale: str = "id"):
    if locale == "id":
        title = f"Invoice {invoice.invoice_number} tersedia"
        body  = f"Invoice untuk pesanan {order.order_number} sudah bisa diunduh."
    else:
        title = f"Invoice {invoice.invoice_number} available"
        body  = f"Invoice for order {order.order_number} is ready to download."

    return _create(
        db, order.user_id,
        NotificationType.invoice_created,
        title, body,
        link=f"/{locale}/dashboard/orders/{order.id}",
        order_id=order.id,
        invoice_id=invoice.id,
    )


# ─── Subscription notifications ──────────────────────────────────────────────

def notify_subscription_new(db: Session, subscription, product, user_id, locale: str = "id"):
    product_name = product.name_id if locale == "id" else product.name_en
    cycle = "Bulanan" if subscription.billing_cycle.value == "monthly" else "Tahunan"
    if locale == "en":
        cycle = "Monthly" if subscription.billing_cycle.value == "monthly" else "Yearly"

    if locale == "id":
        title = f"Langganan aktif — {product_name}"
        body  = f"Langganan {cycle} Anda untuk {product_name} kini aktif."
    else:
        title = f"Subscription activated — {product_name}"
        body  = f"Your {cycle} subscription for {product_name} is now active."

    return _create(
        db, user_id,
        NotificationType.subscription_new,
        title, body,
        link=f"/{locale}/dashboard/subscriptions",
        subscription_id=subscription.id,
    )


def notify_subscription_renewal(db: Session, subscription, product, user_id, locale: str = "id"):
    product_name = product.name_id if locale == "id" else product.name_en

    if locale == "id":
        title = f"Langganan diperpanjang — {product_name}"
        body  = f"Langganan Anda untuk {product_name} telah berhasil diperpanjang."
    else:
        title = f"Subscription renewed — {product_name}"
        body  = f"Your subscription for {product_name} has been successfully renewed."

    return _create(
        db, user_id,
        NotificationType.subscription_renewal,
        title, body,
        link=f"/{locale}/dashboard/subscriptions",
        subscription_id=subscription.id,
    )


def notify_subscription_expiring(db: Session, subscription, product, user_id, days: int, locale: str = "id"):
    product_name = product.name_id if locale == "id" else product.name_en

    if locale == "id":
        title = f"Langganan akan berakhir dalam {days} hari"
        body  = f"Langganan {product_name} Anda akan berakhir dalam {days} hari. Pastikan saldo mencukupi."
    else:
        title = f"Subscription expiring in {days} days"
        body  = f"Your {product_name} subscription expires in {days} days. Please ensure sufficient balance."

    return _create(
        db, user_id,
        NotificationType.subscription_expiring,
        title, body,
        link=f"/{locale}/dashboard/subscriptions",
        subscription_id=subscription.id,
    )


def notify_subscription_cancelled(db: Session, subscription, product, user_id, locale: str = "id"):
    product_name = product.name_id if locale == "id" else product.name_en

    if locale == "id":
        title = f"Langganan dibatalkan — {product_name}"
        body  = "Langganan Anda telah dibatalkan. Anda masih bisa berlangganan kembali kapan saja."
    else:
        title = f"Subscription cancelled — {product_name}"
        body  = "Your subscription has been cancelled. You can re-subscribe at any time."

    return _create(
        db, user_id,
        NotificationType.subscription_cancelled,
        title, body,
        link=f"/{locale}/dashboard/subscriptions",
        subscription_id=subscription.id,
    )


# ─── Refund notifications ─────────────────────────────────────────────────────

def notify_refund_requested(db: Session, refund, order, locale: str = "id"):
    if locale == "id":
        title = f"Permintaan refund diterima — {order.order_number}"
        body  = f"Permintaan refund Rp {refund.amount:,.0f} sedang ditinjau. Kami akan memberi tahu Anda segera."
    else:
        title = f"Refund request received — {order.order_number}"
        body  = f"Your refund request of Rp {refund.amount:,.0f} is under review. We'll notify you shortly."

    return _create(
        db, order.user_id,
        NotificationType.refund_requested,
        title, body,
        link=f"/{locale}/dashboard/orders/{order.id}",
        order_id=order.id,
    )


def notify_refund_approved(db: Session, refund, order, locale: str = "id"):
    if locale == "id":
        title = f"Refund disetujui — {order.order_number}"
        body  = f"Refund Rp {refund.amount:,.0f} Anda telah disetujui dan sedang diproses ke metode pembayaran asal."
    else:
        title = f"Refund approved — {order.order_number}"
        body  = f"Your refund of Rp {refund.amount:,.0f} has been approved and is being processed to your original payment method."

    return _create(
        db, order.user_id,
        NotificationType.refund_approved,
        title, body,
        link=f"/{locale}/dashboard/orders/{order.id}",
        order_id=order.id,
    )


def notify_refund_rejected(db: Session, refund, order, locale: str = "id"):
    reason = refund.rejection_reason or ""
    if locale == "id":
        title = f"Refund ditolak — {order.order_number}"
        body  = f"Permintaan refund Anda tidak dapat diproses.{' Alasan: ' + reason if reason else ''}"
    else:
        title = f"Refund rejected — {order.order_number}"
        body  = f"Your refund request could not be processed.{' Reason: ' + reason if reason else ''}"

    return _create(
        db, order.user_id,
        NotificationType.refund_rejected,
        title, body,
        link=f"/{locale}/dashboard/orders/{order.id}",
        order_id=order.id,
    )


def notify_refund_processed(db: Session, refund, order, locale: str = "id"):
    if locale == "id":
        title = f"Refund berhasil diproses — {order.order_number}"
        body  = f"Rp {refund.amount:,.0f} telah dikembalikan. Dana akan masuk dalam 3–7 hari kerja."
    else:
        title = f"Refund processed — {order.order_number}"
        body  = f"Rp {refund.amount:,.0f} has been refunded. Funds will arrive within 3–7 business days."

    return _create(
        db, order.user_id,
        NotificationType.refund_processed,
        title, body,
        link=f"/{locale}/dashboard/orders/{order.id}",
        order_id=order.id,
    )
