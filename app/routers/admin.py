from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
import uuid
import json
from datetime import datetime

from app.core.database import get_db
from app.core.auth import get_current_user, require_admin
from app.models.user import UserRole
from app.models.product import Product, ProductType, PricingModel, ProductStatus
from app.models.order import Order, OrderStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.upload import (
    save_product_image, save_product_video, save_product_file, delete_upload
)

router = APIRouter(tags=["admin"])


def _require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user or user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _templates(request: Request):
    from app.main import templates
    return templates


def _locale(request: Request) -> str:
    path = request.url.path
    for loc in ["id", "en"]:
        if path.startswith(f"/{loc}/"):
            return loc
    return "id"


# ─── Dashboard Overview ─────────────────────────────────────────────────────

@router.get("/{locale}/admin")
async def admin_dashboard(request: Request, locale: str, db: Session = Depends(get_db)):
    user = _require_admin(request, db)
    from app.main import templates

    total_revenue = db.query(func.sum(Order.amount)).filter(
        Order.status == OrderStatus.paid
    ).scalar() or 0

    total_orders = db.query(func.count(Order.id)).scalar()
    active_subs = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.active
    ).scalar()
    overdue_invoices = db.query(func.count(Invoice.id)).filter(
        Invoice.status == InvoiceStatus.overdue
    ).scalar()

    recent_orders = (
        db.query(Order)
        .order_by(desc(Order.created_at))
        .limit(10)
        .all()
    )

    return templates.TemplateResponse(
        request, "admin/dashboard.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "admin",
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "active_subs": active_subs,
            "overdue_invoices": overdue_invoices,
            "recent_orders": recent_orders,
        },
    )


# ─── Products ───────────────────────────────────────────────────────────────

@router.get("/{locale}/admin/products")
async def admin_products(
    request: Request, locale: str,
    page: int = 1, q: str = "", status: str = "",
    db: Session = Depends(get_db),
):
    user = _require_admin(request, db)
    from app.main import templates

    per_page = 20
    query = db.query(Product)
    if q:
        query = query.filter(
            Product.name_id.ilike(f"%{q}%") | Product.name_en.ilike(f"%{q}%")
        )
    if status:
        query = query.filter(Product.status == status)

    total = query.count()
    products = query.order_by(desc(Product.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return templates.TemplateResponse(
        request, "admin/products.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "admin",
            "products": products,
            "total": total,
            "page": page,
            "per_page": per_page,
            "q": q,
            "status_filter": status,
        },
    )


@router.get("/{locale}/admin/products/new")
async def admin_product_new(request: Request, locale: str, db: Session = Depends(get_db)):
    user = _require_admin(request, db)
    from app.main import templates
    return templates.TemplateResponse(
        request, "admin/product_form.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "admin",
            "product": None,
            "product_types": [t.value for t in ProductType],
            "pricing_models": [p.value for p in PricingModel],
            "product_statuses": [s.value for s in ProductStatus],
        },
    )


@router.post("/{locale}/admin/products/new")
async def admin_product_create(
    request: Request, locale: str,
    slug: str = Form(...),
    name_id: str = Form(...),
    name_en: str = Form(...),
    description_id: str = Form(""),
    description_en: str = Form(""),
    short_desc_id: str = Form(""),
    short_desc_en: str = Form(""),
    type: str = Form(...),
    pricing_model: str = Form(...),
    status: str = Form("draft"),
    price_otf: Optional[str] = Form(None),
    price_monthly: Optional[str] = Form(None),
    price_yearly: Optional[str] = Form(None),
    category: str = Form(""),
    tags: str = Form(""),
    features: str = Form(""),
    sort_order: int = Form(0),
    is_featured: bool = Form(False),
    cover_image: Optional[UploadFile] = File(None),
    preview_video: Optional[UploadFile] = File(None),
    download_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)

    # Check slug unique
    existing = db.query(Product).filter(Product.slug == slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")

    cover_filename = None
    video_filename = None
    file_filename = None

    if cover_image and cover_image.filename:
        cover_filename = await save_product_image(cover_image)
    if preview_video and preview_video.filename:
        video_filename = await save_product_video(preview_video)
    if download_file and download_file.filename:
        file_filename = await save_product_file(download_file)

    product = Product(
        id=uuid.uuid4(),
        slug=slug,
        name_id=name_id, name_en=name_en,
        description_id=description_id or None,
        description_en=description_en or None,
        short_desc_id=short_desc_id or None,
        short_desc_en=short_desc_en or None,
        type=type,
        pricing_model=pricing_model,
        status=status,
        price_otf=float(price_otf) if price_otf else None,
        price_monthly=float(price_monthly) if price_monthly else None,
        price_yearly=float(price_yearly) if price_yearly else None,
        category=category or None,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        features=[f.strip() for f in features.split("\n") if f.strip()],
        sort_order=sort_order,
        is_featured=is_featured,
        cover_image=cover_filename,
        preview_video=video_filename,
        download_file=file_filename,
    )
    db.add(product)
    db.commit()

    return RedirectResponse(url=f"/{locale}/admin/products", status_code=303)


@router.get("/{locale}/admin/products/{product_id}/edit")
async def admin_product_edit(
    request: Request, locale: str, product_id: str, db: Session = Depends(get_db)
):
    user = _require_admin(request, db)
    from app.main import templates

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return templates.TemplateResponse(
        request, "admin/product_form.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "admin",
            "product": product,
            "product_types": [t.value for t in ProductType],
            "pricing_models": [p.value for p in PricingModel],
            "product_statuses": [s.value for s in ProductStatus],
        },
    )


@router.post("/{locale}/admin/products/{product_id}/edit")
async def admin_product_update(
    request: Request, locale: str, product_id: str,
    name_id: str = Form(...),
    name_en: str = Form(...),
    description_id: str = Form(""),
    description_en: str = Form(""),
    short_desc_id: str = Form(""),
    short_desc_en: str = Form(""),
    type: str = Form(...),
    pricing_model: str = Form(...),
    status: str = Form("draft"),
    price_otf: Optional[str] = Form(None),
    price_monthly: Optional[str] = Form(None),
    price_yearly: Optional[str] = Form(None),
    category: str = Form(""),
    tags: str = Form(""),
    features: str = Form(""),
    sort_order: int = Form(0),
    is_featured: bool = Form(False),
    cover_image: Optional[UploadFile] = File(None),
    preview_video: Optional[UploadFile] = File(None),
    download_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if cover_image and cover_image.filename:
        if product.cover_image:
            delete_upload(f"products/images/{product.cover_image}")
        product.cover_image = await save_product_image(cover_image)

    if preview_video and preview_video.filename:
        if product.preview_video:
            delete_upload(f"products/videos/{product.preview_video}")
        product.preview_video = await save_product_video(preview_video)

    if download_file and download_file.filename:
        if product.download_file:
            delete_upload(f"products/files/{product.download_file}")
        product.download_file = await save_product_file(download_file)

    product.name_id = name_id
    product.name_en = name_en
    product.description_id = description_id or None
    product.description_en = description_en or None
    product.short_desc_id = short_desc_id or None
    product.short_desc_en = short_desc_en or None
    product.type = type
    product.pricing_model = pricing_model
    product.status = status
    product.price_otf = float(price_otf) if price_otf else None
    product.price_monthly = float(price_monthly) if price_monthly else None
    product.price_yearly = float(price_yearly) if price_yearly else None
    product.category = category or None
    product.tags = [t.strip() for t in tags.split(",") if t.strip()]
    product.features = [f.strip() for f in features.split("\n") if f.strip()]
    product.sort_order = sort_order
    product.is_featured = is_featured

    db.commit()
    return RedirectResponse(url=f"/{locale}/admin/products", status_code=303)


@router.post("/{locale}/admin/products/{product_id}/delete")
async def admin_product_delete(
    request: Request, locale: str, product_id: str, db: Session = Depends(get_db)
):
    _require_admin(request, db)
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        for path, subdir in [
            (product.cover_image, "products/images"),
            (product.preview_video, "products/videos"),
            (product.download_file, "products/files"),
        ]:
            if path:
                delete_upload(f"{subdir}/{path}")
        db.delete(product)
        db.commit()
    return RedirectResponse(url=f"/{locale}/admin/products", status_code=303)


# ─── Orders ─────────────────────────────────────────────────────────────────

@router.get("/{locale}/admin/orders")
async def admin_orders(
    request: Request, locale: str,
    page: int = 1, status: str = "",
    db: Session = Depends(get_db),
):
    user = _require_admin(request, db)
    from app.main import templates

    per_page = 20
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)

    total = query.count()
    orders = query.order_by(desc(Order.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return templates.TemplateResponse(
        request, "admin/orders.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "admin",
            "orders": orders,
            "total": total,
            "page": page,
            "per_page": per_page,
            "status_filter": status,
            "order_statuses": [s.value for s in OrderStatus],
        },
    )


# ─── Invoices ───────────────────────────────────────────────────────────────

@router.get("/{locale}/admin/invoices")
async def admin_invoices(
    request: Request, locale: str,
    page: int = 1, status: str = "", q: str = "",
    db: Session = Depends(get_db),
):
    user = _require_admin(request, db)
    from app.main import templates
    from app.models.user import User
    from sqlalchemy import or_

    per_page = 20
    query = db.query(Invoice).join(Order).join(User, Order.user_id == User.id)
    if status:
        query = query.filter(Invoice.status == status)
    if q:
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(f"%{q}%"),
                User.name.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
            )
        )

    total = query.count()
    invoices = (
        query.order_by(desc(Invoice.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return templates.TemplateResponse(
        request, "admin/invoices.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "admin",
            "admin_section": "invoices",
            "invoices": invoices,
            "total": total,
            "page": page,
            "per_page": per_page,
            "status_filter": status,
            "q": q,
            "invoice_statuses": [s.value for s in InvoiceStatus],
        },
    )


# ─── Reports ────────────────────────────────────────────────────────────────

@router.get("/{locale}/admin/reports")
async def admin_reports(
    request: Request, locale: str,
    period: str = "30",
    db: Session = Depends(get_db),
):
    user = _require_admin(request, db)
    from app.main import templates
    from datetime import timedelta
    from app.models.user import User

    days = int(period) if period in ["7", "30", "90", "365"] else 30
    since = datetime.utcnow() - timedelta(days=days)

    # Revenue over time (daily)
    revenue_rows = (
        db.query(
            func.date_trunc("day", Order.paid_at).label("day"),
            func.sum(Order.amount).label("total"),
        )
        .filter(Order.status == OrderStatus.paid, Order.paid_at >= since)
        .group_by(func.date_trunc("day", Order.paid_at))
        .order_by(func.date_trunc("day", Order.paid_at))
        .all()
    )

    # Revenue by product type
    from app.models.product import Product
    revenue_by_type = (
        db.query(
            Product.type.label("type"),
            func.sum(Order.amount).label("total"),
            func.count(Order.id).label("count"),
        )
        .join(Product, Order.product_id == Product.id)
        .filter(Order.status == OrderStatus.paid, Order.paid_at >= since)
        .group_by(Product.type)
        .all()
    )

    # Top products
    top_products = (
        db.query(
            Product.name_id.label("name_id"),
            Product.name_en.label("name_en"),
            func.count(Order.id).label("orders"),
            func.sum(Order.amount).label("revenue"),
        )
        .join(Product, Order.product_id == Product.id)
        .filter(Order.status == OrderStatus.paid, Order.paid_at >= since)
        .group_by(Product.id, Product.name_id, Product.name_en)
        .order_by(desc(func.sum(Order.amount)))
        .limit(10)
        .all()
    )

    # Summary stats
    total_revenue = db.query(func.sum(Order.amount)).filter(
        Order.status == OrderStatus.paid, Order.paid_at >= since
    ).scalar() or 0

    total_orders = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.paid, Order.paid_at >= since
    ).scalar() or 0

    new_customers = db.query(func.count(User.id)).filter(
        User.created_at >= since
    ).scalar() or 0

    active_subs = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.active
    ).scalar() or 0

    return templates.TemplateResponse(
        request, "admin/reports.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "admin",
            "admin_section": "reports",
            "period": period,
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "new_customers": new_customers,
            "active_subs": active_subs,
            "revenue_rows": [{"day": str(r.day)[:10], "total": float(r.total)} for r in revenue_rows],
            "revenue_by_type": [{"type": r.type, "total": float(r.total), "count": r.count} for r in revenue_by_type],
            "top_products": top_products,
        },
    )


# ─── Customers ──────────────────────────────────────────────────────────────

@router.get("/{locale}/admin/customers")
async def admin_customers(
    request: Request, locale: str,
    page: int = 1, q: str = "",
    db: Session = Depends(get_db),
):
    from app.models.user import User
    user = _require_admin(request, db)
    from app.main import templates

    per_page = 20
    from sqlalchemy import or_
    query = db.query(User).filter(User.role == UserRole.customer)
    if q:
        query = query.filter(
            or_(User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"))
        )

    total = query.count()
    customers = query.order_by(desc(User.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return templates.TemplateResponse(
        request, "admin/customers.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "admin",
            "customers": customers,
            "total": total,
            "page": page,
            "per_page": per_page,
            "q": q,
        },
    )


@router.post("/{locale}/admin/test-email")
async def admin_test_email(request: Request, locale: str, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    user = _require_admin(request, db)

    try:
        body = await request.json()
        to_email = body.get("email", user.email)
    except Exception:
        to_email = user.email

    from app.services.email import _send, _base_html
    html = _base_html(
        "Test Email — Toko Web Jaya",
        """
        <div class="badge">Test Email</div>
        <h1>Email berhasil dikirim!</h1>
        <p>Konfigurasi SMTP Sumopod berjalan dengan baik.</p>
        <p style="color:#888;font-size:13px">Email ini dikirim dari Toko Web Jaya dev environment.</p>
        """
    )
    ok = _send(to_email, "Test Email — Toko Web Jaya", html)
    if ok:
        return JSONResponse({"ok": True, "message": f"Email terkirim ke {to_email}"})
    return JSONResponse({"ok": False, "message": "Gagal kirim email. Cek log server."}, status_code=500)
