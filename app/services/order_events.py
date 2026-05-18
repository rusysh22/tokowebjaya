"""
Order event logging service.
Append-only audit trail for every order state change.
Call log_event() from checkout handlers, billing tasks, and refund flows.
"""
from sqlalchemy.orm import Session
from app.models.order_event import OrderEvent, OrderEventType, OrderActorType


def log_event(
    db: Session,
    order_id,
    event_type: OrderEventType,
    *,
    actor_type: OrderActorType = OrderActorType.system,
    actor_id=None,
    metadata: dict = None,
    note: str = None,
    commit: bool = True,
) -> OrderEvent:
    ev = OrderEvent(
        order_id=order_id,
        event_type=event_type.value,
        actor_type=actor_type.value,
        actor_id=actor_id,
        metadata=metadata,
        note=note,
    )
    db.add(ev)
    if commit:
        db.commit()
    return ev


# ─── Convenience wrappers ─────────────────────────────────────────────────────

def log_order_created(db, order, actor_id=None):
    return log_event(
        db, order.id, OrderEventType.created,
        actor_type=OrderActorType.customer if actor_id else OrderActorType.system,
        actor_id=actor_id,
        metadata={
            "order_number": order.order_number,
            "amount": int(order.amount),
            "type": order.type.value,
        },
    )


def log_payment_initiated(db, order, method_code: str = None, method_name: str = None):
    return log_event(
        db, order.id, OrderEventType.payment_initiated,
        metadata={"method_code": method_code, "method_name": method_name},
    )


def log_order_paid(db, order):
    return log_event(
        db, order.id, OrderEventType.paid,
        metadata={
            "final_amount": int(order.final_amount or order.amount),
            "gateway": order.payment_gateway.value if order.payment_gateway else None,
            "gateway_reference": order.gateway_reference,
        },
    )


def log_order_failed(db, order, reason: str = None):
    return log_event(
        db, order.id, OrderEventType.failed,
        metadata={"reason": reason},
    )


def log_order_cancelled(db, order, actor_type: OrderActorType = OrderActorType.customer, actor_id=None):
    return log_event(
        db, order.id, OrderEventType.cancelled,
        actor_type=actor_type,
        actor_id=actor_id,
    )


def log_license_issued(db, order, license_id=None):
    return log_event(
        db, order.id, OrderEventType.license_issued,
        metadata={"license_id": str(license_id) if license_id else None},
    )


def log_invoice_created(db, order, invoice_number: str = None):
    return log_event(
        db, order.id, OrderEventType.invoice_created,
        metadata={"invoice_number": invoice_number},
    )


def log_subscription_created(db, order, subscription_id=None):
    return log_event(
        db, order.id, OrderEventType.subscription_created,
        metadata={"subscription_id": str(subscription_id) if subscription_id else None},
    )


def log_refund_requested(db, order, refund_id, amount: int, actor_id=None):
    return log_event(
        db, order.id, OrderEventType.refund_requested,
        actor_type=OrderActorType.customer,
        actor_id=actor_id,
        metadata={"refund_id": str(refund_id), "amount": amount},
    )


def log_refund_approved(db, order, refund_id, actor_id=None):
    return log_event(
        db, order.id, OrderEventType.refund_approved,
        actor_type=OrderActorType.admin,
        actor_id=actor_id,
        metadata={"refund_id": str(refund_id)},
    )


def log_refund_rejected(db, order, refund_id, reason: str = None, actor_id=None):
    return log_event(
        db, order.id, OrderEventType.refund_rejected,
        actor_type=OrderActorType.admin,
        actor_id=actor_id,
        metadata={"refund_id": str(refund_id), "reason": reason},
    )


def log_refunded(db, order, refund_id, amount: int, partial: bool = False):
    event_type = OrderEventType.partially_refunded if partial else OrderEventType.refunded
    return log_event(
        db, order.id, event_type,
        metadata={"refund_id": str(refund_id), "amount": amount},
    )
