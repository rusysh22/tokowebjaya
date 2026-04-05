"""
PromoCode model — discount codes for checkout.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class DiscountType(str, enum.Enum):
    percent = "percent"   # e.g. 20% off
    fixed   = "fixed"     # e.g. Rp 50.000 off


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code            = Column(String(50), unique=True, nullable=False)       # e.g. "HEMAT20"
    description     = Column(String(255), nullable=True)
    discount_type   = Column(Enum(DiscountType), nullable=False, default=DiscountType.percent)
    discount_value  = Column(Numeric(12, 2), nullable=False)                # 20 = 20% or 50000 = Rp50k
    min_amount      = Column(Numeric(12, 2), nullable=True)                 # min order amount (IDR)
    max_discount    = Column(Numeric(12, 2), nullable=True)                 # cap for percent discount (IDR)
    max_uses        = Column(Integer, nullable=True)                         # None = unlimited
    used_count      = Column(Integer, default=0, nullable=False)
    is_active       = Column(Boolean, default=True, nullable=False)
    valid_from      = Column(DateTime, nullable=True)
    valid_until     = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    def is_valid(self, amount_idr: float) -> tuple[bool, str]:
        """Check if promo is currently usable. Returns (ok, reason)."""
        now = datetime.utcnow()
        if not self.is_active:
            return False, "inactive"
        if self.valid_from and now < self.valid_from:
            return False, "not_started"
        if self.valid_until and now > self.valid_until:
            return False, "expired"
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False, "used_up"
        if self.min_amount and amount_idr < float(self.min_amount):
            return False, "below_minimum"
        return True, "ok"

    def calc_discount(self, amount_idr: float) -> float:
        """Return discount amount in IDR (never exceeds original amount)."""
        if self.discount_type == DiscountType.percent:
            disc = amount_idr * float(self.discount_value) / 100
            if self.max_discount:
                disc = min(disc, float(self.max_discount))
        else:
            disc = float(self.discount_value)
        return round(min(disc, amount_idr), 0)
