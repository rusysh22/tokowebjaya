import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class OrderType(str, enum.Enum):
    one_time = "one_time"
    subscription = "subscription"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    cancelled = "cancelled"
    refunded = "refunded"


class PaymentGateway(str, enum.Enum):
    duitku = "duitku"
    mayar = "mayar"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String(50), unique=True, nullable=False, index=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)

    type = Column(Enum(OrderType), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)          # base price (IDR, excl. VAT)
    discount_amount = Column(Numeric(15, 2), default=0)      # promo discount (IDR)
    final_amount = Column(Numeric(15, 2), nullable=True)     # amount charged (IDR, incl. VAT, after discount)
    promo_code = Column(String(50), nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending)

    payment_gateway = Column(Enum(PaymentGateway), nullable=True)
    gateway_reference = Column(String(255), nullable=True)
    gateway_payment_url = Column(Text, nullable=True)

    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")
    invoice = relationship("Invoice", back_populates="order", uselist=False)
