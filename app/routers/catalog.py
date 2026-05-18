"""
Catalog router — product listing and product detail pages.

Routes:
  GET  /{locale}/catalog              — Filterable product grid (type, category, search, sort)
  GET  /{locale}/product/{slug}       — Product detail with related products
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.package import BillingType, PackagePrice, PackageStatus, ProductPackage
from app.models.product import Product, ProductStatus, ProductType

router = APIRouter(tags=["catalog"])


@router.get("/{locale}/catalog")
async def catalog(
    request: Request, locale: str,
    page: int = 1,
    type: str = "",
    category: str = "",
    q: str = "",
    sort: str = "newest",
    db: Session = Depends(get_db),
):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/catalog")

    from app.main import templates
    current_user = get_current_user(request, db)

    per_page = 12
    query = db.query(Product).filter(Product.status == ProductStatus.active)

    if type:
        try:
            query = query.filter(Product.type == ProductType(type))
        except ValueError:
            pass
    if category:
        query = query.filter(Product.category == category)
    if q:
        query = query.filter(
            or_(
                Product.name_id.ilike(f"%{q}%"),
                Product.name_en.ilike(f"%{q}%"),
                Product.description_id.ilike(f"%{q}%"),
            )
        )

    # Subquery: min active package price per product (excluding contact billing)
    min_pkg_price_sq = (
        db.query(
            ProductPackage.product_id,
            func.min(PackagePrice.amount).label("min_price"),
        )
        .join(PackagePrice, PackagePrice.package_id == ProductPackage.id)
        .filter(
            ProductPackage.status == PackageStatus.active,
            PackagePrice.is_active == True,
            PackagePrice.amount.isnot(None),
            PackagePrice.billing_type != BillingType.contact,
        )
        .group_by(ProductPackage.product_id)
        .subquery()
    )

    if sort in ("price_asc", "price_desc"):
        query = query.outerjoin(min_pkg_price_sq, min_pkg_price_sq.c.product_id == Product.id)
        effective_price = func.coalesce(
            min_pkg_price_sq.c.min_price, Product.price_otf, Product.price_monthly
        )
        if sort == "price_asc":
            query = query.order_by(effective_price.asc().nullsfirst())
        else:
            query = query.order_by(effective_price.desc().nullslast())
    else:
        query = query.order_by(Product.sort_order.asc(), Product.created_at.desc())

    total = query.count()
    products = query.offset((page - 1) * per_page).limit(per_page).all()

    # Compute min package price per product for catalog card display
    product_ids = [p.id for p in products]
    min_prices: dict = {}
    if product_ids:
        rows = (
            db.query(
                ProductPackage.product_id,
                func.min(PackagePrice.amount).label("min_price"),
                PackagePrice.billing_type,
            )
            .join(PackagePrice, PackagePrice.package_id == ProductPackage.id)
            .filter(
                ProductPackage.product_id.in_(product_ids),
                ProductPackage.status == PackageStatus.active,
                PackagePrice.is_active == True,
                PackagePrice.amount.isnot(None),
                PackagePrice.billing_type != BillingType.contact,
            )
            .group_by(ProductPackage.product_id, PackagePrice.billing_type)
            .order_by(func.min(PackagePrice.amount).asc())
            .all()
        )
        for r in rows:
            pid = str(r.product_id)
            if pid not in min_prices:
                min_prices[pid] = {"amount": float(r.min_price), "billing_type": r.billing_type.value}

    categories = (
        db.query(Product.category)
        .filter(Product.status == ProductStatus.active, Product.category.isnot(None))
        .distinct()
        .all()
    )
    categories = [c[0] for c in categories if c[0]]

    return templates.TemplateResponse(
        request, "catalog/index.html",
        {
            "locale": locale,
            "current_user": current_user,
            "active_page": "catalog",
            "products": products,
            "total": total,
            "page": page,
            "per_page": per_page,
            "type_filter": type,
            "category_filter": category,
            "q": q,
            "sort": sort,
            "categories": categories,
            "product_types": [t.value for t in ProductType],
            "min_prices": min_prices,
        },
    )


@router.get("/{locale}/product/{slug}")
async def product_detail(
    request: Request, locale: str, slug: str, db: Session = Depends(get_db)
):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/product/{slug}")

    from app.main import templates
    current_user = get_current_user(request, db)

    product = (
        db.query(Product)
        .filter(Product.slug == slug, Product.status == ProductStatus.active)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    related = (
        db.query(Product)
        .filter(
            Product.status == ProductStatus.active,
            Product.type == product.type,
            Product.id != product.id,
        )
        .limit(3)
        .all()
    )

    return templates.TemplateResponse(
        request, "catalog/product_detail.html",
        {
            "locale": locale,
            "current_user": current_user,
            "active_page": "catalog",
            "product": product,
            "related": related,
        },
    )
