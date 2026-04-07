"""
Admin router — protected panel for product management, orders, invoices,
reports, and customer management.

All routes require admin role. Access via /{locale}/admin/*.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType, ProductAvailability
from app.models.contact import ContactMessage, ContactStatus
from app.models.promo import DiscountType, PromoCode
from app.models.invoice import Invoice, InvoiceStatus
from app.models.order import Order, OrderStatus
from app.models.product import PricingModel, Product, ProductStatus, ProductType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import UserRole
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.upload import (
    delete_upload,
    save_product_file,
    save_product_image,
    save_product_video,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def _require_admin(request: Request, db: Session):
    """Verify admin role; raise 403 otherwise."""
    user = get_current_user(request, db)
    if not user or user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


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
    contact_whatsapp: str = Form(""),
    contact_email: str = Form(""),
    contact_address: str = Form(""),
    category: str = Form(""),
    tags: str = Form(""),
    features: str = Form(""),
    sort_order: int = Form(0),
    is_featured: bool = Form(False),
    cover_image: Optional[UploadFile] = File(None),
    preview_video: Optional[UploadFile] = File(None),
    download_file: Optional[UploadFile] = File(None),
    gallery_images: List[UploadFile] = File(default=[]),
    demo_url: str = Form(""),
    license_type: str = Form("none"),
    access_url: str = Form(""),
    guidebook_url: str = Form(""),
    guidebook_text_id: str = Form(""),
    guidebook_text_en: str = Form(""),
    max_activations: int = Form(1),
    license_duration_days: Optional[str] = Form(None),
    webhook_url: str = Form(""),
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
    gallery_filenames = []

    if cover_image and cover_image.filename:
        cover_filename = await save_product_image(cover_image)
    if preview_video and preview_video.filename:
        video_filename = await save_product_video(preview_video)
    if download_file and download_file.filename:
        file_filename = await save_product_file(download_file)
    for gimg in (gallery_images or []):
        if gimg and gimg.filename:
            gallery_filenames.append(await save_product_image(gimg))

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
        contact_whatsapp=contact_whatsapp or None,
        contact_email=contact_email or None,
        contact_address=contact_address or None,
        category=category or None,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        features=[f.strip() for f in features.split("\n") if f.strip()],
        sort_order=sort_order,
        is_featured=is_featured,
        cover_image=cover_filename,
        preview_video=video_filename,
        download_file=file_filename,
        gallery=gallery_filenames,
        demo_url=demo_url or None,
        license_type=license_type or "none",
        access_url=access_url or None,
        guidebook_url=guidebook_url or None,
        guidebook_text_id=guidebook_text_id or None,
        guidebook_text_en=guidebook_text_en or None,
        max_activations=max_activations or 1,
        license_duration_days=int(license_duration_days) if license_duration_days else None,
        webhook_url=webhook_url or None,
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
    contact_whatsapp: str = Form(""),
    contact_email: str = Form(""),
    contact_address: str = Form(""),
    category: str = Form(""),
    tags: str = Form(""),
    features: str = Form(""),
    sort_order: int = Form(0),
    is_featured: bool = Form(False),
    cover_image: Optional[UploadFile] = File(None),
    preview_video: Optional[UploadFile] = File(None),
    download_file: Optional[UploadFile] = File(None),
    gallery_images: List[UploadFile] = File(default=[]),
    gallery_delete: str = Form(""),
    demo_url: str = Form(""),
    license_type: str = Form("none"),
    access_url: str = Form(""),
    guidebook_url: str = Form(""),
    guidebook_text_id: str = Form(""),
    guidebook_text_en: str = Form(""),
    max_activations: int = Form(1),
    license_duration_days: Optional[str] = Form(None),
    webhook_url: str = Form(""),
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

    # Handle gallery: delete selected, add new
    current_gallery = list(product.gallery or [])
    to_delete = [f.strip() for f in gallery_delete.split(",") if f.strip()]
    for fname in to_delete:
        delete_upload(f"products/images/{fname}")
        if fname in current_gallery:
            current_gallery.remove(fname)
    for gimg in (gallery_images or []):
        if gimg and gimg.filename:
            current_gallery.append(await save_product_image(gimg))
    product.gallery = current_gallery

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
    product.contact_whatsapp = contact_whatsapp or None
    product.contact_email = contact_email or None
    product.contact_address = contact_address or None
    product.category = category or None
    product.tags = [t.strip() for t in tags.split(",") if t.strip()]
    product.features = [f.strip() for f in features.split("\n") if f.strip()]
    product.sort_order = sort_order
    product.is_featured = is_featured
    product.demo_url              = demo_url or None
    product.license_type          = license_type or "none"
    product.access_url            = access_url or None
    product.guidebook_url         = guidebook_url or None
    product.guidebook_text_id     = guidebook_text_id or None
    product.guidebook_text_en     = guidebook_text_en or None
    product.max_activations       = max_activations or 1
    product.license_duration_days = int(license_duration_days) if license_duration_days else None
    product.webhook_url           = webhook_url or None

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
        for gfname in (product.gallery or []):
            delete_upload(f"products/images/{gfname}")
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


# ─── Contact Messages ───────────────────────────────────────────────────────

@router.get("/{locale}/admin/contacts")
async def admin_contacts(
    request: Request, locale: str,
    page: int = 1, status: str = "",
    db: Session = Depends(get_db),
):
    user = _require_admin(request, db)
    from app.main import templates
    from datetime import datetime as dt

    per_page = 20
    query = db.query(ContactMessage)
    if status:
        try:
            query = query.filter(ContactMessage.status == ContactStatus(status))
        except ValueError:
            pass

    total = query.count()
    messages = query.order_by(desc(ContactMessage.created_at)) \
                    .offset((page - 1) * per_page).limit(per_page).all()

    unread = db.query(ContactMessage).filter(ContactMessage.status == ContactStatus.new).count()

    return templates.TemplateResponse(
        request, "admin/contacts.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "contacts",
            "messages": messages,
            "total": total,
            "page": page,
            "per_page": per_page,
            "status_filter": status,
            "unread": unread,
            "statuses": [s.value for s in ContactStatus],
        },
    )


@router.post("/{locale}/admin/contacts/{msg_id}/read")
async def admin_contact_mark_read(
    request: Request, locale: str, msg_id: str,
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    from datetime import datetime as dt
    msg = db.query(ContactMessage).filter(ContactMessage.id == msg_id).first()
    if msg and msg.status == ContactStatus.new:
        msg.status = ContactStatus.read
        msg.read_at = dt.utcnow()
        db.commit()
    return RedirectResponse(url=f"/{locale}/admin/contacts", status_code=302)


@router.post("/{locale}/admin/contacts/{msg_id}/delete")
async def admin_contact_delete(
    request: Request, locale: str, msg_id: str,
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    msg = db.query(ContactMessage).filter(ContactMessage.id == msg_id).first()
    if msg:
        db.delete(msg)
        db.commit()
    return RedirectResponse(url=f"/{locale}/admin/contacts", status_code=302)


# ─── Promo Codes ────────────────────────────────────────────────────────────

@router.get("/{locale}/admin/promos")
async def admin_promos(request: Request, locale: str, db: Session = Depends(get_db)):
    user = _require_admin(request, db)
    from app.main import templates
    promos = db.query(PromoCode).order_by(desc(PromoCode.created_at)).all()
    return templates.TemplateResponse(
        request, "admin/promos.html",
        {"locale": locale, "current_user": user, "active_page": "promos",
         "promos": promos, "total": len(promos)},
    )


@router.post("/{locale}/admin/promos/create")
async def admin_promo_create(
    request: Request, locale: str,
    code: str = Form(...),
    description: str = Form(default=""),
    discount_type: str = Form(...),
    discount_value: float = Form(...),
    min_amount: str = Form(default=""),
    max_discount: str = Form(default=""),
    max_uses: str = Form(default=""),
    valid_until: str = Form(default=""),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    from datetime import datetime as dt

    promo = PromoCode(
        id=uuid.uuid4(),
        code=code.strip().upper()[:50],
        description=description.strip() or None,
        discount_type=DiscountType(discount_type),
        discount_value=discount_value,
        min_amount=float(min_amount) if min_amount.strip() else None,
        max_discount=float(max_discount) if max_discount.strip() else None,
        max_uses=int(max_uses) if max_uses.strip() else None,
        valid_until=dt.fromisoformat(valid_until) if valid_until.strip() else None,
    )
    db.add(promo)
    try:
        db.commit()
    except Exception:
        db.rollback()  # duplicate code
    return RedirectResponse(url=f"/{locale}/admin/promos", status_code=302)


@router.post("/{locale}/admin/promos/{promo_id}/toggle")
async def admin_promo_toggle(request: Request, locale: str, promo_id: str, db: Session = Depends(get_db)):
    _require_admin(request, db)
    promo = db.query(PromoCode).filter(PromoCode.id == promo_id).first()
    if promo:
        promo.is_active = not promo.is_active
        db.commit()
    return RedirectResponse(url=f"/{locale}/admin/promos", status_code=302)


@router.post("/{locale}/admin/promos/{promo_id}/delete")
async def admin_promo_delete(request: Request, locale: str, promo_id: str, db: Session = Depends(get_db)):
    _require_admin(request, db)
    promo = db.query(PromoCode).filter(PromoCode.id == promo_id).first()
    if promo:
        db.delete(promo)
        db.commit()
    return RedirectResponse(url=f"/{locale}/admin/promos", status_code=302)


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



# ─── Appointments ────────────────────────────────────────────────────────────

@router.get("/{locale}/admin/appointments")
async def admin_appointments(
    request: Request, locale: str,
    status: str = "all", page: int = 1,
    db: Session = Depends(get_db),
):
    user = _require_admin(request, db)
    from app.main import templates

    per_page = 20
    query = db.query(Appointment)
    if status != "all":
        query = query.filter(Appointment.status == status)
    total = query.count()
    appts = query.order_by(
        Appointment.appt_date.desc(), Appointment.appt_time.desc()
    ).offset((page - 1) * per_page).limit(per_page).all()

    pending_count = db.query(Appointment).filter(
        Appointment.status == AppointmentStatus.pending
    ).count()

    return templates.TemplateResponse(
        request, "admin/appointments.html", {
            "locale":        locale,
            "current_user":  user,
            "active_page":   "appointments",
            "appointments":  appts,
            "total":         total,
            "page":          page,
            "per_page":      per_page,
            "status_filter": status,
            "pending_count": pending_count,
            "statuses":      [s.value for s in AppointmentStatus],
        }
    )


@router.post("/{locale}/admin/appointments/{appt_id}/confirm")
async def admin_appointment_confirm(
    request: Request, locale: str, appt_id: str,
    admin_note: str = Form(""),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if appt and appt.status == AppointmentStatus.pending:
        appt.status       = AppointmentStatus.confirmed
        appt.admin_note   = admin_note or None
        appt.confirmed_at = datetime.utcnow()
        db.commit()
        try:
            from app.services.email import send_appointment_confirmed
            send_appointment_confirmed(appt)
        except Exception:
            pass
    return RedirectResponse(url=f"/{locale}/admin/appointments", status_code=303)


@router.post("/{locale}/admin/appointments/{appt_id}/reject")
async def admin_appointment_reject(
    request: Request, locale: str, appt_id: str,
    admin_note: str = Form(""),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if appt and appt.status in (AppointmentStatus.pending, AppointmentStatus.confirmed):
        appt.status     = AppointmentStatus.rejected
        appt.admin_note = admin_note or None
        db.commit()
        try:
            from app.services.email import send_appointment_rejected
            send_appointment_rejected(appt)
        except Exception:
            pass
    return RedirectResponse(url=f"/{locale}/admin/appointments", status_code=303)


@router.post("/{locale}/admin/appointments/{appt_id}/complete")
async def admin_appointment_complete(
    request: Request, locale: str, appt_id: str,
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if appt and appt.status == AppointmentStatus.confirmed:
        appt.status = AppointmentStatus.completed
        db.commit()
    return RedirectResponse(url=f"/{locale}/admin/appointments", status_code=303)


# ─── Product Availability ─────────────────────────────────────────────────────

@router.get("/{locale}/admin/products/{product_id}/availability")
async def admin_availability(
    request: Request, locale: str, product_id: str,
    db: Session = Depends(get_db),
):
    user = _require_admin(request, db)
    from app.main import templates

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    slots = db.query(ProductAvailability).filter(
        ProductAvailability.product_id == product_id
    ).order_by(ProductAvailability.day_of_week, ProductAvailability.start_time).all()

    day_names = {0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"} if locale=="id" else \
                {0:"Monday",1:"Tuesday",2:"Wednesday",3:"Thursday",4:"Friday",5:"Saturday",6:"Sunday"}

    return templates.TemplateResponse(
        request, "admin/availability.html", {
            "locale":       locale,
            "current_user": user,
            "active_page":  "products",
            "product":      product,
            "slots":        slots,
            "day_names":    day_names,
            "days":         list(range(7)),
        }
    )


@router.post("/{locale}/admin/products/{product_id}/availability/add")
async def admin_availability_add(
    request: Request, locale: str, product_id: str,
    day_of_week: int = Form(...),
    start_time: str  = Form(...),
    end_time: str    = Form(...),
    slot_duration_minutes: int = Form(60),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    from datetime import time as dtime

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404)

    h0, m0 = map(int, start_time.split(":"))
    h1, m1 = map(int, end_time.split(":"))

    slot = ProductAvailability(
        id=uuid.uuid4(),
        product_id=product.id,
        day_of_week=day_of_week,
        start_time=dtime(h0, m0),
        end_time=dtime(h1, m1),
        slot_duration_minutes=slot_duration_minutes,
        is_active=True,
    )
    db.add(slot)
    db.commit()
    return RedirectResponse(url=f"/{locale}/admin/products/{product_id}/availability", status_code=303)


@router.post("/{locale}/admin/availability/{slot_id}/delete")
async def admin_availability_delete(
    request: Request, locale: str, slot_id: str,
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    slot = db.query(ProductAvailability).filter(ProductAvailability.id == slot_id).first()
    if slot:
        product_id = str(slot.product_id)
        db.delete(slot)
        db.commit()
        return RedirectResponse(url=f"/{locale}/admin/products/{product_id}/availability", status_code=303)
    raise HTTPException(status_code=404)


@router.post("/{locale}/admin/availability/{slot_id}/toggle")
async def admin_availability_toggle(
    request: Request, locale: str, slot_id: str,
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    slot = db.query(ProductAvailability).filter(ProductAvailability.id == slot_id).first()
    if slot:
        product_id = str(slot.product_id)
        slot.is_active = not slot.is_active
        db.commit()
        return RedirectResponse(url=f"/{locale}/admin/products/{product_id}/availability", status_code=303)
    raise HTTPException(status_code=404)
