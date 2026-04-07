"""
ProductLicense model — stores license keys, passwords, credentials, and
download tokens delivered to users after a successful order.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from app.core.database import Base


class LicenseType(str, enum.Enum):
    token      = "token"       # SaaS / software — API-validated token
    password   = "password"    # File encryption password / ZIP password
    credential = "credential"  # username + password (service access)
    download   = "download"    # Signed download URL (ebook, template)
    none       = "none"        # No license needed (manual delivery)


class ProductLicense(Base):
    __tablename__ = "product_licenses"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id        = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id      = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)

    # Delivery type
    license_type    = Column(String(20), nullable=False, default=LicenseType.token)

    # Credentials (license_key stored as plaintext for display, password hashed)
    license_key      = Column(String(255), nullable=True)   # TWJ-XXXX-XXXX-XXXX-XXXX
    license_password = Column(String(255), nullable=True)   # plaintext — shown once, user must save
    license_username = Column(String(255), nullable=True)   # for credential type
    access_url       = Column(String(500), nullable=True)   # URL aplikasi / landing page produk

    # Validity
    expires_at       = Column(DateTime, nullable=True)      # None = lifetime
    grace_until      = Column(DateTime, nullable=True)      # expires_at + 3 days grace
    max_activations  = Column(Integer, default=1)
    activated_count  = Column(Integer, default=0)

    # Download tracking
    download_count      = Column(Integer, default=0)
    max_downloads       = Column(Integer, default=5)
    last_downloaded_at  = Column(DateTime, nullable=True)

    # Status
    is_active      = Column(Boolean, default=True)
    revoked_at     = Column(DateTime, nullable=True)
    revoked_reason = Column(Text, nullable=True)

    # Reminder tracking
    reminded_7d      = Column(Boolean, default=False)
    reminded_3d      = Column(Boolean, default=False)
    reminded_expired = Column(Boolean, default=False)

    # Flexible extra data: domain_lock, seats, version, last_validated_ip, etc.
    license_metadata = Column(JSONB, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order        = relationship("Order",        foreign_keys=[order_id])
    user         = relationship("User",         foreign_keys=[user_id])
    product      = relationship("Product",      foreign_keys=[product_id])
    subscription = relationship("Subscription", foreign_keys=[subscription_id])
    activations  = relationship("LicenseActivation", back_populates="license", cascade="all, delete-orphan")

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_in_grace(self) -> bool:
        """True if past expires_at but still within grace period."""
        if not self.is_expired or not self.grace_until:
            return False
        return datetime.utcnow() <= self.grace_until

    @property
    def is_valid(self) -> bool:
        """Valid if active and not expired (grace period counts as valid)."""
        if not self.is_active:
            return False
        if self.expires_at is None:
            return True
        return datetime.utcnow() <= (self.grace_until or self.expires_at)

    @property
    def days_until_expiry(self) -> int | None:
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)


class LicenseActivation(Base):
    """Tracks per-device activations for a license."""
    __tablename__ = "license_activations"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_id  = Column(UUID(as_uuid=True), ForeignKey("product_licenses.id", ondelete="CASCADE"), nullable=False)
    device_id   = Column(String(255), nullable=True)
    ip_address  = Column(String(45), nullable=True)
    user_agent  = Column(Text, nullable=True)
    activated_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    is_active    = Column(Boolean, default=True)

    license = relationship("ProductLicense", back_populates="activations")
