"""
ContactMessage model — stores messages submitted via the contact form.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ContactStatus(str, enum.Enum):
    new     = "new"
    read    = "read"
    replied = "replied"


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(255), nullable=False)
    email      = Column(String(255), nullable=False)
    subject    = Column(String(500), nullable=True)
    message    = Column(Text, nullable=False)
    status     = Column(Enum(ContactStatus), default=ContactStatus.new, nullable=False)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at    = Column(DateTime, nullable=True)
