"""
Appointment models:
  - ProductAvailability  : per-product weekly schedule set by admin
  - Appointment          : a booking made by a user for a product
"""
import enum
from datetime import datetime, date, time
from sqlalchemy import (
    Column, String, Text, Date, Time, DateTime,
    Enum, ForeignKey, Boolean, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class AppointmentType(str, enum.Enum):
    demo    = "demo"    # product demo / presentation
    call    = "call"    # phone / video call
    meeting = "meeting" # offline meeting


class AppointmentStatus(str, enum.Enum):
    pending   = "pending"    # waiting admin confirmation
    confirmed = "confirmed"  # admin approved
    cancelled = "cancelled"  # cancelled by user or admin
    completed = "completed"  # meeting done
    rejected  = "rejected"   # admin rejected


class ProductAvailability(Base):
    """
    Weekly availability slots for a product.
    One row = one day-of-week + time window.
    day_of_week: 0=Mon, 1=Tue, ..., 6=Sun
    slot_duration_minutes: length of each appointment slot (default 60)
    """
    __tablename__ = "product_availability"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id            = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    day_of_week           = Column(Integer, nullable=False)   # 0–6
    start_time            = Column(Time, nullable=False)      # e.g. 09:00
    end_time              = Column(Time, nullable=False)      # e.g. 17:00
    slot_duration_minutes = Column(Integer, default=60)
    is_active             = Column(Boolean, default=True)

    product = relationship("Product", backref="availability_slots")


class Appointment(Base):
    __tablename__ = "appointments"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id",    ondelete="CASCADE"), nullable=False)

    appt_type  = Column(Enum(AppointmentType),   nullable=False, default=AppointmentType.demo)
    status     = Column(Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.pending)

    appt_date  = Column(Date, nullable=False)
    appt_time  = Column(Time, nullable=False)          # WIB (UTC+7)
    timezone   = Column(String(50), default="Asia/Jakarta")  # user's local tz label

    notes      = Column(Text, nullable=True)           # message from user
    admin_note = Column(Text, nullable=True)           # rejection/confirmation note from admin

    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    product = relationship("Product", backref="appointments")
    user    = relationship("User",    backref="appointments")
