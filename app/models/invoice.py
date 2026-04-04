import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class InvoiceStatus(str, enum.Enum):
    unpaid = "unpaid"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)

    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)

    amount = Column(Numeric(15, 2), nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.unpaid)

    due_date = Column(DateTime, nullable=False)
    paid_date = Column(DateTime, nullable=True)

    pdf_path = Column(String(500), nullable=True)
    email_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("Order", back_populates="invoice")
