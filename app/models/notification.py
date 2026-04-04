import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class NotificationType(str, enum.Enum):
    order_paid       = "order_paid"
    order_failed     = "order_failed"
    invoice_created  = "invoice_created"
    subscription_new = "subscription_new"
    subscription_renewal = "subscription_renewal"
    subscription_expiring = "subscription_expiring"
    subscription_cancelled = "subscription_cancelled"
    general          = "general"


class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type       = Column(Enum(NotificationType), nullable=False, default=NotificationType.general)
    title      = Column(String(255), nullable=False)
    body       = Column(Text, nullable=True)
    link       = Column(String(500), nullable=True)   # optional CTA URL
    is_read    = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")
