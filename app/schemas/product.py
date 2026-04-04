from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal
from app.models.product import ProductType, PricingModel, ProductStatus


class ProductCreate(BaseModel):
    slug: str
    name_id: str
    name_en: str
    description_id: Optional[str] = None
    description_en: Optional[str] = None
    short_desc_id: Optional[str] = None
    short_desc_en: Optional[str] = None
    type: ProductType
    pricing_model: PricingModel = PricingModel.one_time
    status: ProductStatus = ProductStatus.draft
    price_otf: Optional[Decimal] = None
    price_monthly: Optional[Decimal] = None
    price_yearly: Optional[Decimal] = None
    category: Optional[str] = None
    tags: list[str] = []
    features: list[str] = []
    sort_order: int = 0
    is_featured: bool = False

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        import re
        v = v.lower().strip()
        v = re.sub(r"[^a-z0-9-]", "-", v)
        v = re.sub(r"-+", "-", v).strip("-")
        return v


class ProductUpdate(BaseModel):
    name_id: Optional[str] = None
    name_en: Optional[str] = None
    description_id: Optional[str] = None
    description_en: Optional[str] = None
    short_desc_id: Optional[str] = None
    short_desc_en: Optional[str] = None
    type: Optional[ProductType] = None
    pricing_model: Optional[PricingModel] = None
    status: Optional[ProductStatus] = None
    price_otf: Optional[Decimal] = None
    price_monthly: Optional[Decimal] = None
    price_yearly: Optional[Decimal] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    features: Optional[list[str]] = None
    sort_order: Optional[int] = None
    is_featured: Optional[bool] = None
