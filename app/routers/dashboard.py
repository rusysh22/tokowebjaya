"""
Dashboard router — authenticated user pages.

Routes:
  GET  /{locale}/dashboard                          — Overview (redirects admin to /admin)
  GET  /{locale}/dashboard/orders                   — Paginated order history
  GET  /{locale}/dashboard/invoices                 — Paginated invoice list
  GET  /{locale}/dashboard/orders/{id}/receipt      — Order receipt view
  GET  /{locale}/dashboard/invoices/{id}/download   — Download invoice PDF
  GET  /{locale}/dashboard/subscriptions            — Active / past subscriptions
  GET  /{locale}/dashboard/api-keys                 — Manage API keys
  POST /{locale}/dashboard/api-keys/create          — Create new API key
  POST /{locale}/dashboard/api-keys/{id}/revoke     — Revoke API key
  POST /{locale}/dashboard/subscriptions/{id}/cancel — Cancel subscription
"""
import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.api_key import ApiKey, ApiKeyScope
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.package import BillingType, PackagePrice, ProductPackage
from app.models.subscription import Subscription, SubscriptionStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])


def _require_user(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        from urllib.parse import quote
        path = request.url.path
        next_url = path + (f"?{request.url.query}" if request.url.query else "")
        for loc in ["id", "en"]:
            if path.startswith(f"/{loc}/"):
                return RedirectResponse(url=f"/{loc}/login?next={quote(next_url)}"), None
        return RedirectResponse(url=f"/id/login?next={quote(next_url)}"), None
    return None, user


@router.get("/{locale}/dashboard")
async def dashboard(request: Request, locale: str, db: Session = Depends(get_db)):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/dashboard")

    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    # Redirect admin to admin panel
    from app.models.user import UserRole  # noqa: PLC0415
    if user.role == UserRole.admin:
        return RedirectResponse(url=f"/{locale}/admin")

    from app.main import templates

    recent_orders = (
        db.query(Order).filter(Order.user_id == user.id)
        .order_by(desc(Order.created_at)).limit(5).all()
    )
    active_subs = (
        db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        ).all()
    )
    recent_invoices = (
        db.query(Invoice)
        .join(Order)
        .filter(Order.user_id == user.id)
        .order_by(desc(Invoice.created_at)).limit(5).all()
    )

    return templates.TemplateResponse(
        request, "dashboard/index.html",
        {
            "locale": locale,
            "current_user": user,
            "active_page": "dashboard",
            "recent_orders": recent_orders,
            "active_subs": active_subs,
            "recent_invoices": recent_invoices,
        },
    )


@router.get("/{locale}/dashboard/orders")
async def dashboard_orders(request: Request, locale: str, page: int = 1, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    from app.main import templates
    per_page = 10
    total = db.query(Order).filter(Order.user_id == user.id).count()
    orders = (
        db.query(Order).filter(Order.user_id == user.id)
        .order_by(desc(Order.created_at))
        .offset((page - 1) * per_page).limit(per_page).all()
    )
    return templates.TemplateResponse(
        request, "dashboard/orders.html",
        {"locale": locale, "current_user": user, "orders": orders, "total": total, "page": page, "per_page": per_page},
    )


@router.get("/{locale}/dashboard/invoices")
async def dashboard_invoices(request: Request, locale: str, page: int = 1, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    from app.main import templates
    per_page = 10
    query = db.query(Invoice).join(Order).filter(Order.user_id == user.id)
    total = query.count()
    invoices = query.order_by(desc(Invoice.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return templates.TemplateResponse(
        request, "dashboard/invoices.html",
        {"locale": locale, "current_user": user, "invoices": invoices, "total": total, "page": page, "per_page": per_page},
    )


@router.get("/{locale}/dashboard/orders/{order_id}/receipt")
async def order_receipt(request: Request, locale: str, order_id: str, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404)

    invoice = db.query(Invoice).filter(Invoice.order_id == order_id).first()

    from app.main import templates
    return templates.TemplateResponse(
        request, "dashboard/receipt.html",
        {"locale": locale, "current_user": user, "order": order, "invoice": invoice},
    )


@router.get("/{locale}/dashboard/invoices/{invoice_id}/download")
async def download_invoice(request: Request, locale: str, invoice_id: str, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    invoice = (
        db.query(Invoice).join(Order)
        .filter(Invoice.id == invoice_id, Order.user_id == user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Generate PDF on-demand if not yet created
    if not invoice.pdf_path or not (Path(settings.UPLOAD_DIR) / invoice.pdf_path).exists():
        try:
            from app.services.invoice import _generate_pdf
            pdf_path = _generate_pdf(invoice, invoice.order, db)
            invoice.pdf_path = pdf_path
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")

    pdf_path = Path(settings.UPLOAD_DIR) / invoice.pdf_path
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Invoice PDF file missing")

    return FileResponse(
        path=str(pdf_path),
        filename=f"{invoice.invoice_number}.pdf",
        media_type="application/pdf",
    )


@router.get("/{locale}/dashboard/subscriptions")
async def dashboard_subscriptions(request: Request, locale: str, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    from app.main import templates
    subs = db.query(Subscription).filter(Subscription.user_id == user.id).order_by(
        Subscription.status, Subscription.next_billing_date
    ).all()

    # Load available packages per active subscription for upgrade/downgrade UI
    sub_packages: dict = {}
    for sub in subs:
        if sub.status == SubscriptionStatus.active and sub.product_id:
            pkgs = (
                db.query(ProductPackage)
                .filter(
                    ProductPackage.product_id == sub.product_id,
                    ProductPackage.status == "active",
                )
                .order_by(ProductPackage.sort_order)
                .all()
            )
            sub_packages[str(sub.id)] = pkgs

    return templates.TemplateResponse(
        request, "dashboard/subscriptions.html",
        {"locale": locale, "current_user": user, "subscriptions": subs, "sub_packages": sub_packages},
    )


@router.get("/{locale}/dashboard/api-keys")
async def dashboard_api_keys(request: Request, locale: str, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    from app.main import templates
    keys = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user.id, ApiKey.is_active == True)
        .order_by(desc(ApiKey.created_at))
        .all()
    )
    return templates.TemplateResponse(
        request, "dashboard/api_keys.html",
        {
            "locale": locale,
            "current_user": user,
            "keys": keys,
            "scopes": [s.value for s in ApiKeyScope],
            "new_key": request.query_params.get("new_key"),
        },
    )


@router.post("/{locale}/dashboard/api-keys/create")
async def dashboard_create_api_key(request: Request, locale: str, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    form = await request.form()
    name = str(form.get("name", "My API Key"))[:255]
    scope = str(form.get("scope", "read"))

    try:
        scope_enum = ApiKeyScope(scope)
    except ValueError:
        scope_enum = ApiKeyScope.read

    raw_key, prefix = ApiKey.generate_key()
    api_key = ApiKey(
        user_id=user.id,
        name=name,
        key_hash=ApiKey.hash_key(raw_key),
        key_prefix=prefix,
        scope=scope_enum,
    )
    db.add(api_key)
    db.commit()

    # Pass new key once via redirect (flash-style)
    return RedirectResponse(
        url=f"/{locale}/dashboard/api-keys?new_key={quote(raw_key)}",
        status_code=303,
    )


@router.post("/{locale}/dashboard/api-keys/{key_id}/revoke")
async def dashboard_revoke_api_key(request: Request, locale: str, key_id: str, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    if key:
        key.is_active = False
        db.commit()

    return RedirectResponse(url=f"/{locale}/dashboard/api-keys", status_code=303)


@router.post("/{locale}/dashboard/subscriptions/{sub_id}/cancel")
async def cancel_subscription(request: Request, locale: str, sub_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    from datetime import datetime  # noqa: PLC0415 — avoid circular import
    sub = db.query(Subscription).filter(
        Subscription.id == sub_id, Subscription.user_id == user.id
    ).first()
    if sub and sub.status == SubscriptionStatus.active:
        sub.status = SubscriptionStatus.cancelled
        sub.cancelled_at = datetime.utcnow()
        db.commit()
        try:
            from app.services.notification import notify_subscription_cancelled
            notify_subscription_cancelled(db, sub, sub.product, user.id, locale)
        except Exception:
            pass
        try:
            from app.services.email import send_subscription_cancelled
            background_tasks.add_task(send_subscription_cancelled, sub, sub.product, user, locale)
        except Exception:
            pass

    return RedirectResponse(url=f"/{locale}/dashboard/subscriptions", status_code=303)


@router.post("/{locale}/dashboard/subscriptions/{sub_id}/schedule-change")
async def schedule_subscription_change(
    request: Request, locale: str, sub_id: str,
    db: Session = Depends(get_db),
):
    """AJAX — schedule package upgrade/downgrade effective at next renewal."""
    from fastapi.responses import JSONResponse
    redirect, user = _require_user(request, db)
    if redirect:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid request"}, status_code=400)

    package_price_id = str(body.get("package_price_id", "")).strip()
    if not package_price_id:
        return JSONResponse({"detail": "package_price_id required"}, status_code=400)

    sub = db.query(Subscription).filter(
        Subscription.id == sub_id, Subscription.user_id == user.id,
        Subscription.status == SubscriptionStatus.active,
    ).first()
    if not sub:
        return JSONResponse({"detail": "Active subscription not found"}, status_code=404)

    pkg_price = db.query(PackagePrice).filter(
        PackagePrice.id == package_price_id,
        PackagePrice.is_active == True,
    ).first()
    if not pkg_price:
        return JSONResponse({"detail": "Package price not found"}, status_code=404)

    new_pkg = pkg_price.package
    if not new_pkg or new_pkg.product_id != sub.product_id:
        return JSONResponse({"detail": "Package does not belong to this product"}, status_code=400)

    if str(new_pkg.id) == str(sub.package_id):
        return JSONResponse({"detail": "Already on this package"}, status_code=400)

    sub.scheduled_package_id = new_pkg.id
    db.commit()

    effective_date = sub.next_billing_date.strftime("%d %b %Y")
    return JSONResponse({
        "status": "scheduled",
        "package_name": new_pkg.name_id if locale == "id" else new_pkg.name_en,
        "effective_date": effective_date,
    })


@router.post("/{locale}/dashboard/subscriptions/{sub_id}/cancel-change")
async def cancel_subscription_change(
    request: Request, locale: str, sub_id: str,
    db: Session = Depends(get_db),
):
    """AJAX — cancel a pending scheduled package change."""
    from fastapi.responses import JSONResponse
    redirect, user = _require_user(request, db)
    if redirect:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    sub = db.query(Subscription).filter(
        Subscription.id == sub_id, Subscription.user_id == user.id,
    ).first()
    if not sub:
        return JSONResponse({"detail": "Subscription not found"}, status_code=404)

    sub.scheduled_package_id = None
    db.commit()
    return JSONResponse({"status": "cancelled"})
