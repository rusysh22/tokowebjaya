import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, Enum, Numeric, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class ProductType(str, enum.Enum):
    ebook = "ebook"
    course = "course"
    software = "software"
    template = "template"
    service = "service"


class PricingModel(str, enum.Enum):
    one_time = "one_time"
    subscription = "subscription"
    both = "both"
    contact_seller = "contact_seller"


class ProductStatus(str, enum.Enum):
    active = "active"
    draft = "draft"
    archived = "archived"


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(255), unique=True, nullable=False, index=True)

    # Bilingual fields
    name_id = Column(String(255), nullable=False)
    name_en = Column(String(255), nullable=False)
    description_id = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    short_desc_id = Column(String(500), nullable=True)
    short_desc_en = Column(String(500), nullable=True)

    type = Column(Enum(ProductType), nullable=False)
    pricing_model = Column(Enum(PricingModel), default=PricingModel.one_time)
    status = Column(Enum(ProductStatus), default=ProductStatus.draft)

    # Pricing
    price_otf = Column(Numeric(15, 2), nullable=True)
    price_monthly = Column(Numeric(15, 2), nullable=True)
    price_yearly = Column(Numeric(15, 2), nullable=True)

    # Media
    cover_image = Column(String(500), nullable=True)
    preview_video = Column(String(500), nullable=True)
    download_file = Column(String(500), nullable=True)
    gallery = Column(JSON, default=list)
    demo_url = Column(String(500), nullable=True)

    # Contact seller info (used when pricing_model = contact_seller)
    contact_whatsapp = Column(String(30), nullable=True)   # e.g. "6281234567890"
    contact_email    = Column(String(255), nullable=True)
    contact_address  = Column(Text, nullable=True)

    # Metadata
    category = Column(String(100), nullable=True)
    tags = Column(JSON, default=list)
    features = Column(JSON, default=list)
    sort_order = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="product")
    subscriptions = relationship("Subscription", back_populates="product")
