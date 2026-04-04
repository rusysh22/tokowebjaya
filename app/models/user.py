import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class AuthProvider(str, enum.Enum):
    google = "google"
    email = "email"


class UserRole(str, enum.Enum):
    admin = "admin"
    customer = "customer"


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    banned = "banned"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    google_id = Column(String(255), unique=True, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    # Email+password auth
    password_hash = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    auth_provider = Column(Enum(AuthProvider), default=AuthProvider.google, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.customer, nullable=False)
    status = Column(Enum(UserStatus), default=UserStatus.active, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")
    notifications = relationship("Notification", back_populates="user", order_by="Notification.created_at.desc()")
