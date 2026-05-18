import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class RefundStatus(str, enum.Enum):
    pending   = "pending"
    approved  = "approved"
    rejected  = "rejected"
    processed = "processed"
    failed    = "failed"


class Refund(Base):
    __tablename__ = "refunds"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id          = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id           = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    reviewed_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    status            = Column(Enum(RefundStatus), nullable=False, default=RefundStatus.pending, index=True)
    amount            = Column(Integer, nullable=False)          # IDR, in full rupiah
    reason            = Column(Text, nullable=False)             # customer reason
    admin_note        = Column(Text, nullable=True)              # admin's internal note
    rejection_reason  = Column(Text, nullable=True)              # shown to customer on reject
    gateway_refund_id = Column(String(255), nullable=True)       # Duitku refund reference

    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at  = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    order    = relationship("Order",  back_populates="refunds")
    user     = relationship("User",   foreign_keys=[user_id],    back_populates="refunds")
    reviewer = relationship("User",   foreign_keys=[reviewed_by])
