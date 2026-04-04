"""
B2B External API v1

Authentication: Bearer token (API key)
  Header: Authorization: Bearer twj_xxxxx

Endpoints:
  GET  /api/v1/products          — List active products
  GET  /api/v1/products/{slug}   — Get product detail
  GET  /api/v1/orders            — List caller's orders
  GET  /api/v1/orders/{id}       — Get order detail
  GET  /api/v1/subscriptions     — List caller's subscriptions
  POST /api/v1/keys              — Create API key (requires login session, not API key)
  GET  /api/v1/keys              — List caller's API keys
  DELETE /api/v1/keys/{id}       — Revoke API key
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.api_key import ApiKey, ApiKeyScope
from app.models.product import Product, ProductStatus
from app.models.order import Order, OrderStatus
from app.models.subscription import Subscription, SubscriptionStatus

router = APIRouter(prefix="/api/v1", tags=["api_v1"])


# ─── Auth dependency ─────────────────────────────────────────────────────────

def _get_api_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Resolve API key from Authorization: Bearer header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="API key required. Use: Authorization: Bearer <key>")

    raw_key = authorization.removeprefix("Bearer ").strip()
    key_hash = ApiKey.hash_key(raw_key)

    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True,
    ).first()

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="API key expired")

    # Update last_used_at (fire-and-forget — do not block)
    try:
        api_key.last_used_at = datetime.utcnow()
        db.commit()
    except Exception:
        pass

    return api_key


def _require_write(api_key: ApiKey = Depends(_get_api_user)):
    if api_key.scope == ApiKeyScope.read:
        raise HTTPException(status_code=403, detail="This API key only has read access")
    return api_key


# ─── Products ────────────────────────────────────────────────────────────────

@router.get("/products")
def api_list_products(
    page: int = 1,
    per_page: int = 20,
    type: str = "",
    q: str = "",
    api_key: ApiKey = Depends(_get_api_user),
    db: Session = Depends(get_db),
):
    """List all active products."""
    per_page = min(per_page, 100)
    query = db.query(Product).filter(Product.status == ProductStatus.active)

    if type:
        query = query.filter(Product.type == type)
    if q:
        from sqlalchemy import or_
        query = query.filter(
            or_(Product.name_id.ilike(f"%{q}%"), Product.name_en.ilike(f"%{q}%"))
        )

    total = query.count()
    products = query.order_by(Product.sort_order.asc(), Product.created_at.desc()) \
                    .offset((page - 1) * per_page).limit(per_page).all()

    return {
        "data": [_serialize_product(p) for p in products],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }


@router.get("/products/{slug}")
def api_get_product(
    slug: str,
    api_key: ApiKey = Depends(_get_api_user),
    db: Session = Depends(get_db),
):
    """Get a single product by slug."""
    product = db.query(Product).filter(
        Product.slug == slug, Product.status == ProductStatus.active
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"data": _serialize_product(product)}


# ─── Orders ──────────────────────────────────────────────────────────────────

@router.get("/orders")
def api_list_orders(
    page: int = 1,
    per_page: int = 20,
    status: str = "",
    api_key: ApiKey = Depends(_get_api_user),
    db: Session = Depends(get_db),
):
    """List orders belonging to the API key owner."""
    per_page = min(per_page, 100)
    query = db.query(Order).filter(Order.user_id == api_key.user_id)

    if status:
        try:
            query = query.filter(Order.status == OrderStatus(status))
        except ValueError:
            pass

    total = query.count()
    orders = query.order_by(desc(Order.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "data": [_serialize_order(o) for o in orders],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }


@router.get("/orders/{order_id}")
def api_get_order(
    order_id: str,
    api_key: ApiKey = Depends(_get_api_user),
    db: Session = Depends(get_db),
):
    """Get a single order. Must belong to the API key owner."""
    order = db.query(Order).filter(
        Order.id == order_id, Order.user_id == api_key.user_id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"data": _serialize_order(order)}


# ─── Subscriptions ───────────────────────────────────────────────────────────

@router.get("/subscriptions")
def api_list_subscriptions(
    api_key: ApiKey = Depends(_get_api_user),
    db: Session = Depends(get_db),
):
    """List subscriptions belonging to the API key owner."""
    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == api_key.user_id)
        .order_by(desc(Subscription.created_at))
        .all()
    )
    return {"data": [_serialize_subscription(s) for s in subs]}


# ─── API Key Management ──────────────────────────────────────────────────────

@router.get("/keys")
def api_list_keys(
    request: Request,
    db: Session = Depends(get_db),
):
    """List all API keys for the authenticated session user (uses session cookie, not API key)."""
    current_user = get_current_user(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    keys = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id, ApiKey.is_active == True)
        .order_by(desc(ApiKey.created_at))
        .all()
    )
    return {"data": [_serialize_key(k) for k in keys]}


@router.post("/keys")
def api_create_key(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Create a new API key. Uses session cookie for auth (not API key).
    Returns the raw key ONCE — store it securely, it cannot be retrieved again.
    """
    current_user = get_current_user(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    import json as _json
    try:
        body = _json.loads(request.state._body) if hasattr(request.state, "_body") else {}
    except Exception:
        body = {}

    name = body.get("name", "API Key")
    scope = body.get("scope", "read")

    try:
        scope_enum = ApiKeyScope(scope)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid scope. Choose: {[s.value for s in ApiKeyScope]}")

    raw_key, prefix = ApiKey.generate_key()

    api_key = ApiKey(
        user_id=current_user.id,
        name=name[:255],
        key_hash=ApiKey.hash_key(raw_key),
        key_prefix=prefix,
        scope=scope_enum,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return JSONResponse(
        status_code=201,
        content={
            "data": {
                "id": str(api_key.id),
                "name": api_key.name,
                "key": raw_key,  # Only returned once
                "key_prefix": prefix,
                "scope": scope,
                "created_at": api_key.created_at.isoformat(),
            },
            "warning": "Store this key securely. It will not be shown again.",
        },
    )


@router.post("/keys/{key_id}/revoke")
def api_revoke_key(
    key_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Revoke (deactivate) an API key. Uses session cookie for auth."""
    current_user = get_current_user(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id, ApiKey.user_id == current_user.id
    ).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    db.commit()
    return {"message": "API key revoked"}


# ─── Serializers ─────────────────────────────────────────────────────────────

def _serialize_product(p: Product) -> dict:
    return {
        "id": str(p.id),
        "slug": p.slug,
        "name_id": p.name_id,
        "name_en": p.name_en,
        "short_desc_id": p.short_desc_id,
        "short_desc_en": p.short_desc_en,
        "type": p.type.value if p.type else None,
        "pricing_model": p.pricing_model.value if p.pricing_model else None,
        "price_otf": float(p.price_otf) if p.price_otf else None,
        "price_monthly": float(p.price_monthly) if p.price_monthly else None,
        "price_yearly": float(p.price_yearly) if p.price_yearly else None,
        "category": p.category,
        "tags": p.tags or [],
        "features": p.features or [],
        "is_featured": p.is_featured,
        "cover_image_url": f"/static/uploads/products/images/{p.cover_image}" if p.cover_image else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _serialize_order(o: Order) -> dict:
    return {
        "id": str(o.id),
        "order_number": o.order_number,
        "product_id": str(o.product_id),
        "product_name": o.product.name_id if o.product else None,
        "type": o.type.value if o.type else None,
        "amount": float(o.amount),
        "status": o.status.value if o.status else None,
        "payment_gateway": o.payment_gateway.value if o.payment_gateway else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _serialize_subscription(s: Subscription) -> dict:
    return {
        "id": str(s.id),
        "product_id": str(s.product_id),
        "product_name": s.product.name_id if s.product else None,
        "status": s.status.value if s.status else None,
        "billing_cycle": s.billing_cycle.value if s.billing_cycle else None,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "next_billing_date": s.next_billing_date.isoformat() if s.next_billing_date else None,
        "cancelled_at": s.cancelled_at.isoformat() if s.cancelled_at else None,
    }


def _serialize_key(k: ApiKey) -> dict:
    return {
        "id": str(k.id),
        "name": k.name,
        "key_prefix": k.key_prefix + "...",
        "scope": k.scope.value if k.scope else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }
