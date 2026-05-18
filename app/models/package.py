import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from app.core.database import Base


class BillingType(str, enum.Enum):
    one_time = "one_time"
    monthly  = "monthly"
    yearly   = "yearly"
    contact  = "contact"


class PackageStatus(str, enum.Enum):
    active   = "active"
    draft    = "draft"
    archived = "archived"


class LimitValueType(str, enum.Enum):
    int  = "int"
    bool = "bool"
    enum = "enum"


class ProductPackage(Base):
    """One tier/plan for a product (e.g. Standard, Premium, Enterprise)."""
    __tablename__ = "product_packages"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    code       = Column(String(50),  nullable=False)   # "standard", "premium"
    name_id    = Column(String(255), nullable=False)
    name_en    = Column(String(255), nullable=False)
    tagline_id = Column(String(500), nullable=True)
    tagline_en = Column(String(500), nullable=True)
    description_id = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)

    is_default  = Column(Boolean, nullable=False, default=False)
    is_popular  = Column(Boolean, nullable=False, default=False)
    sort_order  = Column(Integer, nullable=False, default=0)

    # License / delivery config (dipindah dari Product)
    license_type          = Column(String(20),  nullable=False, default="none")
    max_activations       = Column(Integer,     nullable=False, default=1)
    license_duration_days = Column(Integer,     nullable=True)
    access_url            = Column(String(500), nullable=True)
    guidebook_url         = Column(String(500), nullable=True)
    guidebook_text_id     = Column(Text,        nullable=True)
    guidebook_text_en     = Column(Text,        nullable=True)
    webhook_url           = Column(String(500), nullable=True)
    download_file         = Column(String(500), nullable=True)

    status     = Column(String(20), nullable=False, default=PackageStatus.draft.value)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("product_id", "code", name="uq_package_code"),
    )

    product  = relationship("Product", back_populates="packages")
    prices   = relationship("PackagePrice",   back_populates="package", cascade="all, delete-orphan",
                            order_by="PackagePrice.billing_type")
    features = relationship("PackageFeature", back_populates="package", cascade="all, delete-orphan",
                            order_by="PackageFeature.sort_order")
    limits   = relationship("PackageLimit",   back_populates="package", cascade="all, delete-orphan")

    def get_price(self, billing_type: BillingType) -> "PackagePrice | None":
        return next((p for p in self.prices if p.billing_type == billing_type and p.is_active), None)

    def snapshot_limits(self) -> dict:
        """Return a dict of limits suitable for storing in license_metadata['limits']."""
        result = {}
        for lim in self.limits:
            schema = lim.schema
            if lim.is_unlimited:
                result[schema.key] = None   # None = unlimited
            elif schema.value_type == LimitValueType.int:
                result[schema.key] = lim.value_int
            elif schema.value_type == LimitValueType.bool:
                result[schema.key] = lim.value_bool
            else:
                result[schema.key] = lim.value_text
        return result


class PackagePrice(Base):
    """One billing option for a package (one_time, monthly, yearly, or contact)."""
    __tablename__ = "package_prices"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id   = Column(UUID(as_uuid=True), ForeignKey("product_packages.id", ondelete="CASCADE"), nullable=False)

    billing_type = Column(Enum(BillingType), nullable=False)
    amount       = Column(Numeric(15, 2), nullable=True)   # NULL for contact
    currency     = Column(String(3), nullable=False, default="IDR")
    is_active    = Column(Boolean, nullable=False, default=True)

    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("package_id", "billing_type", name="uq_package_price_billing"),
    )

    package = relationship("ProductPackage", back_populates="prices")


class PackageFeature(Base):
    """A ✓/✗ bullet point for the pricing comparison table."""
    __tablename__ = "package_features"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(UUID(as_uuid=True), ForeignKey("product_packages.id", ondelete="CASCADE"), nullable=False)

    label_id   = Column(String(500), nullable=False)
    label_en   = Column(String(500), nullable=False)
    included   = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    package = relationship("ProductPackage", back_populates="features")


class ProductLimitSchema(Base):
    """
    Defines WHICH quota dimensions a product has.
    Stored once per product. e.g. product "Helpdesk AI" declares:
      key=max_agents (int), key=storage_gb (int), key=priority_support (bool)
    """
    __tablename__ = "product_limit_schemas"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id              = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    key                     = Column(String(100), nullable=False)   # "max_agents"
    label_id                = Column(String(255), nullable=False)
    label_en                = Column(String(255), nullable=False)
    unit                    = Column(String(50),  nullable=True)    # "agent", "GB" — None for booleans
    value_type              = Column(Enum(LimitValueType), nullable=False, default=LimitValueType.int)
    enum_options            = Column(JSONB, nullable=True)           # ["basic","advanced"] for value_type=enum
    is_unlimited_allowed    = Column(Boolean, nullable=False, default=True)
    sort_order              = Column(Integer, nullable=False, default=0)
    is_visible_on_pricing_page = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("product_id", "key", name="uq_limit_schema_key"),
    )

    product      = relationship("Product", back_populates="limit_schemas")
    package_limits = relationship("PackageLimit", back_populates="schema", cascade="all, delete-orphan")


class PackageLimit(Base):
    """
    The actual quota value for one dimension in one package.
    e.g. Premium -> max_agents schema -> value_int=15
         Standard -> max_agents schema -> value_int=3
         Enterprise -> max_agents schema -> is_unlimited=True
    """
    __tablename__ = "package_limits"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(UUID(as_uuid=True), ForeignKey("product_packages.id", ondelete="CASCADE"), nullable=False)
    schema_id  = Column(UUID(as_uuid=True), ForeignKey("product_limit_schemas.id", ondelete="CASCADE"), nullable=False)

    value_int  = Column(Integer,      nullable=True)
    value_bool = Column(Boolean,      nullable=True)
    value_text = Column(String(255),  nullable=True)  # for enum value_type
    is_unlimited = Column(Boolean,    nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("package_id", "schema_id", name="uq_package_limit"),
    )

    package = relationship("ProductPackage",    back_populates="limits")
    schema  = relationship("ProductLimitSchema", back_populates="package_limits")

    def resolved_value(self):
        """Return the typed value, or None if unlimited."""
        if self.is_unlimited:
            return None
        if self.schema.value_type == LimitValueType.int:
            return self.value_int
        if self.schema.value_type == LimitValueType.bool:
            return self.value_bool
        return self.value_text
