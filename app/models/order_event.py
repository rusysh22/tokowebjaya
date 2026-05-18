import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class OrderEventType(str, enum.Enum):
    created              = "created"
    payment_initiated    = "payment_initiated"
    paid                 = "paid"
    failed               = "failed"
    cancelled            = "cancelled"
    refund_requested     = "refund_requested"
    refund_approved      = "refund_approved"
    refund_rejected      = "refund_rejected"
    refunded             = "refunded"
    partially_refunded   = "partially_refunded"
    license_issued       = "license_issued"
    invoice_created      = "invoice_created"
    subscription_created = "subscription_created"
    subscription_renewed = "subscription_renewed"
    note_added           = "note_added"


class OrderActorType(str, enum.Enum):
    system   = "system"
    customer = "customer"
    admin    = "admin"


class OrderEvent(Base):
    __tablename__ = "order_events"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id   = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    actor_type = Column(String(20), nullable=False, default=OrderActorType.system.value)
    actor_id   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    metadata   = Column(JSONB, nullable=True)
    note       = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    order = relationship("Order", back_populates="events")
    actor = relationship("User", foreign_keys=[actor_id])
