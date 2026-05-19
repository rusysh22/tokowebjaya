"""
Checkout router — handles the full purchase flow:
  1. Review page  GET  /{locale}/checkout/{product_id}
  2. Validate promo (AJAX)           POST /checkout/promo/validate
  3. Select payment method page GET  /{locale}/checkout/{product_id}/select-payment
  4. Payment methods API (AJAX) GET  /checkout/payment-methods
  5. Create payment (AJAX/JSON) POST /{locale}/checkout/{product_id}/create-payment
  6. Payment instruction page   GET  /{locale}/checkout/payment/{order_id}
  7. Return page after callback  GET  /{locale}/checkout/return/{order_id}
  8. Payment status polling      GET  /checkout/status/{order_id}
  9. Duitku webhook              POST /checkout/callback/duitku
  10. Mayar webhook              POST /checkout/callback/mayar

Pricing contract (IDR):
  base_amount    = product price (excl. VAT)
  discount       = promo discount applied to base_amount
  subtotal       = base_amount - discount
  vat            = subtotal * VAT_RATE (11% PPN for IDR)
  service_fee    = payment method fee from Duitku (flat or %)
  final_amount   = subtotal + vat + service_fee  ← this is what Duitku charges
"""
import logging
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote as urlquote, urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.order import Order, OrderStatus, OrderType, PaymentGateway
from app.models.package import BillingType, PackagePrice, ProductPackage
from app.models.product import Product, ProductStatus
from app.models.promo import PromoCode
from app.models.subscription import BillingCycle, Subscription, SubscriptionStatus
from app.services.payment import _method_type, duitku, generate_order_number, mayar
from app.services import order_events as ev

logger = logging.getLogger(__name__)
router = APIRouter(tags=["checkout"])


# ─── Helpers ────────────────────────────────────────────────────────────────

def _calc_final_amount(base_idr: float, promo: PromoCode | None) -> dict:
    """
    Calculate final charge amount (IDR) after discount and VAT.
    Returns dict with all breakdown fields.
    """
    discount = promo.calc_discount(base_idr) if promo else 0.0
    subtotal = base_idr - discount
    vat_rate = settings.VAT_RATE_IDR          # 0.11
    vat_amt  = round(subtotal * vat_rate, 0)
    final    = round(subtotal + vat_amt, 0)
    return {
        "base":            base_idr,
        "discount":        discount,
        "subtotal":        subtotal,
        "vat_rate":        vat_rate,
        "vat_amount":      vat_amt,
        "final":           final,
        "promo_code":      promo.code if promo else None,
    }


def _resolve_promo(code: str, base_idr: float, db: Session) -> tuple[PromoCode | None, str]:
    """Look up and validate a promo code. Returns (promo_obj, error_reason)."""
    if not code:
        return None, ""
    promo = db.query(PromoCode).filter(
        PromoCode.code == code.strip().upper(),
        PromoCode.is_active == True,
    ).first()
    if not promo:
        return None, "not_found"
    ok, reason = promo.is_valid(base_idr)
    if not ok:
        return None, reason
    return promo, ""


def _parse_service_fee(total_fee_str: str, amount: int) -> int:
    """
    Parse Duitku totalFee field into IDR integer.
    Duitku returns either a flat string ("4500") or percentage string ("1.5%").
    """
    if not total_fee_str:
        return 0
    s = str(total_fee_str).strip()
    if s.endswith("%"):
        pct = float(s[:-1]) / 100
        return int(round(amount * pct))
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _compute_service_fee_server(payment_method: str, charge_amount: int) -> int:
    """
    Look up service fee from Redis-cached Duitku payment methods.
    Returns 0 on cache miss (safe fallback — Duitku will apply its own fee).
    """
    try:
        import json as _json
        import redis as _redis
        cache_key = f"duitku:methods:{charge_amount}"
        _r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
        cached = _r.get(cache_key)
        if cached:
            methods = _json.loads(cached)
            for m in methods:
                if m.get("paymentMethod", "").upper() == payment_method.upper():
                    return _parse_service_fee(m.get("totalFee", "0"), charge_amount)
    except Exception:
        pass
    return 0


def _resolve_checkout_pricing(
    product_id: str,
    package_price_id: str,
    order_type_param: str,
    billing_cycle_param: str,
    db: Session,
) -> tuple:
    """
    Resolve product, package, package_price, base_amount, order_type, billing_cycle.

    Price source priority:
      1. package_price_id provided → use that PackagePrice directly
      2. No package_price_id but product has active packages → auto-select:
           - is_default package first, then first active package
           - matching billing_type from order_type_param/billing_cycle_param
      3. No packages at all → fallback to product.price_otf/monthly/yearly
         (for simple products / contact_seller without package setup)

    Returns (product, package, package_price, base_amount, order_type, billing_cycle).
    """
    package_price: PackagePrice | None = None
    package: ProductPackage | None = None
    product: Product | None = None
    base_amount: float | None = None
    order_type = order_type_param
    billing_cycle = billing_cycle_param

    # ── Path 1: explicit package_price_id ────────────────────────────────────
    if package_price_id:
        try:
            package_price = db.query(PackagePrice).filter(
                PackagePrice.id == package_price_id,
                PackagePrice.is_active == True,
            ).first()
        except Exception:
            pass
        if package_price:
            package = package_price.package
            if package:
                product = db.query(Product).filter(
                    Product.id == package.product_id,
                    Product.status == ProductStatus.active,
                ).first()
            if package_price.amount:
                base_amount   = float(package_price.amount)
                order_type    = "one_time" if package_price.billing_type == BillingType.one_time else "subscription"
                billing_cycle = package_price.billing_type.value if package_price.billing_type.value in ("monthly", "yearly") else "monthly"

    # ── Load product if not yet resolved ─────────────────────────────────────
    if not product:
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.status == ProductStatus.active,
        ).first()

    # ── Path 2: auto-select from active packages ──────────────────────────────
    if not base_amount and product and not package_price_id:
        # Determine target billing_type from caller params
        if order_type_param == "one_time":
            target_billing = BillingType.one_time
        elif order_type_param == "subscription" and billing_cycle_param == "yearly":
            target_billing = BillingType.yearly
        else:
            target_billing = BillingType.monthly

        active_pkgs = [p for p in product.packages if p.status == "active"]
        # Prefer is_default, then first in sort order
        candidates = sorted(active_pkgs, key=lambda p: (not p.is_default, p.sort_order))

        for candidate in candidates:
            pr = next(
                (p for p in candidate.prices if p.billing_type == target_billing and p.is_active and p.amount),
                None,
            )
            # If exact billing type not found, take any available price
            if not pr:
                pr = next(
                    (p for p in candidate.prices if p.is_active and p.amount),
                    None,
                )
            if pr:
                package       = candidate
                package_price = pr
                base_amount   = float(pr.amount)
                order_type    = "one_time" if pr.billing_type == BillingType.one_time else "subscription"
                billing_cycle = pr.billing_type.value if pr.billing_type.value in ("monthly", "yearly") else "monthly"
                break

    # ── Path 3: product-level prices (no packages configured) ────────────────
    if not base_amount and product:
        if order_type == "one_time" and product.price_otf:
            base_amount = float(product.price_otf)
        elif order_type == "subscription":
            if billing_cycle == "yearly" and product.price_yearly:
                base_amount = float(product.price_yearly)
            elif product.price_monthly:
                base_amount = float(product.price_monthly)

    return product, package, package_price, base_amount, order_type, billing_cycle


_PAYMENT_EXPIRY_MINUTES: dict[str, int] = {
    "va":      1440,   # Virtual Account — 24 hours
    "retail":  1440,   # Alfamart / Indomaret — 24 hours
    "qris":    30,     # QRIS — 30 minutes
    "ewallet": 15,     # E-Wallet deep link — 15 minutes (user redirected immediately)
    "cc":      120,    # Credit card — 2 hours
    "other":   1440,
}


_PROMO_ERRORS = {
    "not_found":     {"id": "Kode promo tidak ditemukan.", "en": "Promo code not found."},
    "expired":       {"id": "Kode promo sudah kadaluarsa.", "en": "Promo code has expired."},
    "not_started":   {"id": "Kode promo belum aktif.", "en": "Promo code is not yet active."},
    "used_up":       {"id": "Kode promo sudah habis digunakan.", "en": "Promo code usage limit reached."},
    "below_minimum": {"id": "Minimum pembelian tidak terpenuhi.", "en": "Minimum purchase amount not met."},
    "inactive":      {"id": "Kode promo tidak aktif.", "en": "Promo code is inactive."},
}


@router.get("/{locale}/checkout/failed")
async def checkout_failed(request: Request, locale: str, order: str = "", db: Session = Depends(get_db)):
    from app.main import templates
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        request, "checkout/failed.html",
        {"locale": locale, "current_user": current_user, "order_id": order},
    )


@router.get("/{locale}/checkout/pending")
async def checkout_pending(request: Request, locale: str, order: str = "", db: Session = Depends(get_db)):
    from app.main import templates
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        request, "checkout/pending.html",
        {"locale": locale, "current_user": current_user, "order_id": order},
    )


@router.get("/checkout/payment-methods")
async def get_payment_methods(request: Request, amount: int = 0, db: Session = Depends(get_db)):
    """
    AJAX — return active Duitku payment methods for given amount.
    Cached in Redis for 10 minutes per amount bracket.
    """
    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    # Use Redis cache if available
    cache_key = f"duitku:methods:{amount}"
    import json as _json
    try:
        import redis as _redis
        from app.core.config import settings as _s
        _r = _redis.from_url(_s.REDIS_URL, decode_responses=True)
        cached = _r.get(cache_key)
        if cached:
            return JSONResponse({"methods": _json.loads(cached)})
    except Exception:
        pass

    try:
        methods = await duitku.get_payment_methods(amount or 10000)
    except Exception as e:
        logger.error(f"[payment-methods] {e}")
        if settings.APP_ENV == "development":
            from app.services.payment import _method_type as _mt
            _mock = [
                {"paymentMethod": "BC", "paymentName": "BCA VA", "paymentImage": "https://images.duitku.com/hotlink-ok/BCA.SVG", "totalFee": "0"},
                {"paymentMethod": "BR", "paymentName": "BRI VA", "paymentImage": "https://images.duitku.com/hotlink-ok/BR.PNG", "totalFee": "0"},
                {"paymentMethod": "I1", "paymentName": "BNI VA", "paymentImage": "https://images.duitku.com/hotlink-ok/I1.PNG", "totalFee": "0"},
                {"paymentMethod": "M2", "paymentName": "MANDIRI VA H2H", "paymentImage": "https://images.duitku.com/hotlink-ok/MV.PNG", "totalFee": "0"},
                {"paymentMethod": "B1", "paymentName": "CIMB NIAGA VA", "paymentImage": "https://images.duitku.com/hotlink-ok/B1.PNG", "totalFee": "0"},
                {"paymentMethod": "BV", "paymentName": "BSI VA", "paymentImage": "https://images.duitku.com/hotlink-ok/BSI.PNG", "totalFee": "0"},
                {"paymentMethod": "SP", "paymentName": "SHOPEEPAY QRIS", "paymentImage": "https://images.duitku.com/hotlink-ok/SHOPEEPAY.PNG", "totalFee": "0"},
                {"paymentMethod": "LQ", "paymentName": "LINKAJA QRIS", "paymentImage": "https://images.duitku.com/hotlink-ok/LINKAJA.PNG", "totalFee": "0"},
                {"paymentMethod": "OV", "paymentName": "OVO", "paymentImage": "https://images.duitku.com/hotlink-ok/OV.PNG", "totalFee": "0"},
                {"paymentMethod": "DA", "paymentName": "DANA", "paymentImage": "https://images.duitku.com/hotlink-ok/DA.PNG", "totalFee": "0"},
                {"paymentMethod": "SA", "paymentName": "SHOPEEPAY APP", "paymentImage": "https://images.duitku.com/hotlink-ok/SHOPEEPAY.PNG", "totalFee": "0"},
                {"paymentMethod": "IR", "paymentName": "INDOMARET", "paymentImage": "https://images.duitku.com/hotlink-ok/IR.PNG", "totalFee": "0"},
                {"paymentMethod": "FT", "paymentName": "ALFAMART", "paymentImage": "https://images.duitku.com/hotlink-ok/RETAIL.PNG", "totalFee": "0"},
                {"paymentMethod": "VC", "paymentName": "CREDIT CARD", "paymentImage": "https://images.duitku.com/hotlink-ok/VC.PNG", "totalFee": "0"},
            ]
            for m in _mock:
                m["method_type"] = _mt(m["paymentMethod"])
            methods = _mock
        else:
            return JSONResponse({"detail": "Failed to load payment methods"}, status_code=502)

    # Sort by popularity priority
    _PRIORITY = {
        "BC": 1, "BR": 2, "I1": 3, "M2": 4, "B1": 5, "BV": 6, "BT": 7,
        "SP": 10, "LQ": 11, "NQ": 12, "GQ": 13,
        "OV": 20, "DA": 21, "SA": 22, "LA": 23, "SL": 24, "OL": 25, "JP": 26,
        "IR": 30, "FT": 31,
        "VC": 40,
    }
    methods.sort(key=lambda m: _PRIORITY.get(m.get("paymentMethod", ""), 99))

    try:
        _r.setex(cache_key, 600, _json.dumps(methods))
    except Exception:
        pass

    return JSONResponse({"methods": methods})


@router.get("/{locale}/checkout/{product_id}/select-payment")
async def checkout_select_payment(
    request: Request, locale: str, product_id: str,
    package_price_id: str = "",
    type: str = "one_time", cycle: str = "monthly",
    promo: str = "",
    db: Session = Depends(get_db),
):
    """Payment method selection page."""
    import uuid as _uuid
    try:
        _uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=404)

    current_user = get_current_user(request, db)
    if not current_user:
        qs: dict = {"type": type, "cycle": cycle}
        if package_price_id:
            qs["package_price_id"] = package_price_id
        if promo:
            qs["promo"] = promo
        next_path = f"/{locale}/checkout/{product_id}/select-payment?" + urlencode(qs)
        return RedirectResponse(url=f"/{locale}/login?next={urlquote(next_path)}")

    product, _, package_price, base_amount, order_type, billing_cycle = _resolve_checkout_pricing(
        product_id, package_price_id, type, cycle, db
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not base_amount:
        raise HTTPException(status_code=400, detail="Invalid pricing configuration")

    promo_obj, _ = _resolve_promo(promo, base_amount, db)
    breakdown = _calc_final_amount(base_amount, promo_obj)

    from app.main import templates
    return templates.TemplateResponse(
        request, "checkout/select_payment.html",
        {
            "locale": locale,
            "current_user": current_user,
            "product": product,
            "package_price_id": package_price_id,
            "order_type": order_type,
            "billing_cycle": billing_cycle,
            "promo_code": promo,
            "breakdown": breakdown,
            "base_amount": base_amount,
        },
    )


@router.post("/checkout/promo/validate")
async def validate_promo(request: Request, db: Session = Depends(get_db)):
    """AJAX — validate a promo code and return discount breakdown."""
    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"valid": False, "reason": "login_required"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"valid": False, "reason": "invalid_request"}, status_code=400)

    code     = str(body.get("code", "")).strip().upper()
    base_idr = float(body.get("base_amount", 0))
    locale   = str(body.get("locale", "id"))

    if not code:
        return JSONResponse({"valid": False, "reason": "empty"})

    promo, reason = _resolve_promo(code, base_idr, db)
    if not promo:
        lang = locale if locale in ("id", "en") else "id"
        if reason == "below_minimum":
            min_val = float(promo.min_amount or 0) if promo else 0
            reason_msg = (
                f"Minimum pembelian Rp {min_val:,.0f}." if lang == "id"
                else f"Minimum purchase Rp {min_val:,.0f}."
            )
        else:
            err = _PROMO_ERRORS.get(reason, {"id": "Kode promo tidak valid.", "en": "Invalid promo code."})
            reason_msg = err[lang]
        return JSONResponse({"valid": False, "reason": reason, "message": reason_msg})

    breakdown = _calc_final_amount(base_idr, promo)
    return JSONResponse({
        "valid":           True,
        "code":            promo.code,
        "description":     promo.description or "",
        "discount_type":   promo.discount_type.value,
        "discount_value":  float(promo.discount_value),
        "discount_amount": breakdown["discount"],
        "subtotal":        breakdown["subtotal"],
        "vat_amount":      breakdown["vat_amount"],
        "final":           breakdown["final"],
    })


@router.get("/{locale}/checkout/{product_id}")
async def checkout_review(
    request: Request, locale: str, product_id: str,
    package_price_id: str = "",
    type: str = "one_time", cycle: str = "monthly",
    currency: str = "",
    db: Session = Depends(get_db),
):
    import uuid as _uuid
    try:
        _uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/catalog")

    current_user = get_current_user(request, db)
    if not current_user:
        qs: dict = {}
        if package_price_id:
            qs["package_price_id"] = package_price_id
        if type and type != "one_time":
            qs["type"] = type
            qs["cycle"] = cycle
        next_path = f"/{locale}/checkout/{product_id}"
        if qs:
            next_path += "?" + urlencode(qs)
        return RedirectResponse(url=f"/{locale}/login?next={urlquote(next_path)}")

    # Resolve currency
    if not currency or currency not in settings.SUPPORTED_CURRENCIES:
        currency = settings.DEFAULT_CURRENCY

    product, package, package_price, amount_idr, order_type, billing_cycle = _resolve_checkout_pricing(
        product_id, package_price_id, type, cycle, db
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not amount_idr:
        raise HTTPException(status_code=400, detail="Invalid pricing configuration")

    from app.core.currency import get_display_prices
    pricing = get_display_prices(amount_idr, currency, include_vat=True)

    now = datetime.utcnow()
    available_promos = db.query(PromoCode).filter(
        PromoCode.is_active == True,
        (PromoCode.valid_until == None) | (PromoCode.valid_until > now),
        (PromoCode.valid_from == None)  | (PromoCode.valid_from <= now),
        (PromoCode.max_uses == None)    | (PromoCode.used_count < PromoCode.max_uses),
        (PromoCode.min_amount == None)  | (PromoCode.min_amount <= amount_idr),
    ).all()

    from app.main import templates
    return templates.TemplateResponse(
        request, "checkout/review.html",
        {
            "locale": locale,
            "current_user": current_user,
            "product": product,
            "package": package,
            "package_price": package_price,
            "package_price_id": package_price_id,
            "order_type": order_type,
            "billing_cycle": billing_cycle,
            "currency": currency,
            "pricing": pricing,
            "amount": amount_idr,
            "supported_currencies": settings.SUPPORTED_CURRENCIES,
            "available_promos": available_promos,
        },
    )


@router.post("/{locale}/checkout/{product_id}/create-payment")
async def checkout_create_payment(
    request: Request, locale: str, product_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    AJAX endpoint — creates order and calls Duitku V2 for specific payment method.
    Body: { order_type, billing_cycle, promo_code, payment_method, payment_method_name, service_fee }
    """

    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    package_price_id    = str(body.get("package_price_id", "")).strip()
    promo_code          = str(body.get("promo_code", "")).strip().upper()
    payment_method      = str(body.get("payment_method", "")).strip().upper()
    payment_method_name = str(body.get("payment_method_name", "")).strip()
    order_type_param    = str(body.get("order_type", "one_time"))
    billing_cycle_param = str(body.get("billing_cycle", "monthly"))

    if not payment_method:
        return JSONResponse({"detail": "Payment method is required"}, status_code=400)

    # Resolve product + pricing via shared helper
    product, package, package_price, base_amount, order_type, billing_cycle = _resolve_checkout_pricing(
        product_id, package_price_id, order_type_param, billing_cycle_param, db
    )
    if not product:
        return JSONResponse({"detail": "Product not found"}, status_code=404)
    if not base_amount:
        return JSONResponse({"detail": "Invalid amount"}, status_code=400)
    if package_price and package_price.billing_type == BillingType.contact:
        return JSONResponse({"detail": "Contact-seller packages cannot be checked out directly"}, status_code=400)
    if package and package.status != "active":
        return JSONResponse({"detail": "Package is not active"}, status_code=400)

    # Resolve promo
    promo, promo_error = _resolve_promo(promo_code, base_amount, db)
    if promo_code and not promo:
        return JSONResponse({"detail": f"Promo tidak valid: {promo_error}"}, status_code=400)

    # Calculate base charge (base - discount + VAT), then add server-computed service fee
    breakdown = _calc_final_amount(base_amount, promo)
    service_fee   = _compute_service_fee_server(payment_method, int(breakdown["final"]))
    charge_amount = int(breakdown["final"]) + service_fee
    logger.info(
        "Checkout breakdown — base=%.0f discount=%.0f subtotal=%.0f vat=%.0f service_fee=%d final=%d",
        breakdown["base"], breakdown["discount"], breakdown["subtotal"],
        breakdown["vat_amount"], service_fee, charge_amount,
    )

    # Cancel any existing pending order for same user+product+package_price to avoid zombie orders
    cutoff = datetime.utcnow() - timedelta(minutes=30)
    existing_pending = db.query(Order).filter(
        Order.user_id    == current_user.id,
        Order.product_id == product.id,
        Order.status     == OrderStatus.pending,
        Order.created_at >= cutoff,
    ).first()
    if existing_pending:
        existing_pending.status = OrderStatus.cancelled
        db.commit()

    order_enum_type = OrderType.one_time if order_type == "one_time" else OrderType.subscription
    order_number = generate_order_number()
    order = Order(
        id=uuid.uuid4(),
        order_number=order_number,
        user_id=current_user.id,
        product_id=product.id,
        package_id=package.id if package else None,
        package_price_id=package_price.id if package_price else None,
        type=order_enum_type,
        amount=base_amount,
        discount_amount=breakdown["discount"],
        final_amount=charge_amount,
        promo_code=promo.code if promo else None,
        status=OrderStatus.pending,
        payment_gateway=PaymentGateway.duitku,
        payment_method_code=payment_method,
        payment_method_name=payment_method_name,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return_url = f"{settings.BASE_URL}/{locale}/checkout/return/{order.id}"
    product_name = product.name_id if locale == "id" else product.name_en

    try:
        result = await duitku.create_payment_v2(
            order_number=order_number,
            amount=charge_amount,
            payment_method=payment_method,
            product_name=product_name,
            customer_name=current_user.name,
            customer_email=current_user.email,
            return_url=return_url,
        )

        logger.info(f"[create-payment] duitku response keys={list(result.keys())} full={result}")
        reference  = result.get("reference") or result.get("merchantOrderId")
        va_number  = result.get("vaNumber") or result.get("virtualAccountNumber") or result.get("accountNumber") or ""
        qr_string  = result.get("qrString") or result.get("qrCode") or result.get("qrisString") or ""
        pay_code   = result.get("paymentCode") or result.get("payCode") or result.get("rcode") or ""
        payment_url = result.get("paymentUrl") or result.get("payment_url") or ""

        expiry_minutes = _PAYMENT_EXPIRY_MINUTES.get(_method_type(payment_method), 1440)
        order.gateway_reference    = reference
        order.gateway_payment_url  = payment_url
        order.payment_expired_at   = datetime.utcnow() + timedelta(minutes=expiry_minutes)
        order.va_number            = va_number
        order.qr_string            = qr_string
        order.payment_code         = pay_code
        db.commit()

        return JSONResponse({
            "order_id":     str(order.id),
            "order_number": order_number,
            "final_amount": charge_amount,
            "redirect_to":  f"/{locale}/checkout/payment/{order.id}",
        })

    except Exception as e:
        order.status = OrderStatus.failed
        db.commit()
        logger.error(f"[create-payment] error={e}")
        # Extract Duitku error message if available
        duitku_msg = str(e)
        return JSONResponse({"detail": f"Payment gateway error: {duitku_msg}"}, status_code=502)



@router.get("/{locale}/checkout/payment/{order_id}")
async def checkout_payment(
    request: Request, locale: str, order_id: str,
    db: Session = Depends(get_db),
):
    """Payment waiting page — user can open Duitku from here and re-open if closed."""
    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url=f"/{locale}/login")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404)

    # Ownership check — only the order's owner can view this page
    if str(order.user_id) != str(current_user.id):
        raise HTTPException(status_code=403)

    # If already paid, go straight to return page
    if order.status == OrderStatus.paid:
        return RedirectResponse(url=f"/{locale}/checkout/return/{order_id}", status_code=303)

    # Calculate seconds left until expiry
    seconds_left = 0
    if order.payment_expired_at:
        delta = order.payment_expired_at - datetime.utcnow()
        seconds_left = max(0, int(delta.total_seconds()))

    from app.main import templates
    from app.services.payment_guide import get_guide
    return templates.TemplateResponse(
        request, "checkout/payment.html",
        {
            "locale": locale,
            "current_user": current_user,
            "order": order,
            "seconds_left": seconds_left,
            "method_type": _method_type(order.payment_method_code or ""),
            "payment_guide": get_guide(order.payment_method_code or ""),
        },
    )


@router.get("/{locale}/checkout/return/{order_id}")
async def checkout_return(
    request: Request, locale: str, order_id: str,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url=f"/{locale}/login")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404)

    if str(order.user_id) != str(current_user.id):
        raise HTTPException(status_code=403)

    from app.main import templates
    return templates.TemplateResponse(
        request, "checkout/return.html",
        {"locale": locale, "current_user": current_user, "order": order},
    )


@router.get("/checkout/status/{order_id}")
async def checkout_status(request: Request, order_id: str, db: Session = Depends(get_db)):
    """AJAX endpoint — returns current order status. Requires login + ownership."""
    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"status": "unauthorized"}, status_code=401)

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return JSONResponse({"status": "not_found"}, status_code=404)

    # Ownership check
    if str(order.user_id) != str(current_user.id):
        return JSONResponse({"status": "forbidden"}, status_code=403)

    return JSONResponse({"status": order.status.value})


# ─── Webhooks ───────────────────────────────────────────────────────────────

@router.post("/checkout/callback/duitku")
async def duitku_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Duitku Pop API sends JSON callback
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception:
        data = {}

    merchant_code = data.get("merchantCode")
    amount = int(data.get("amount", 0))
    order_id = data.get("merchantOrderId")
    signature = data.get("signature")
    result_code = data.get("resultCode")

    logger.info(f"[duitku callback] data={data}")

    if merchant_code and signature:
        if not duitku.verify_callback(merchant_code, amount, order_id, signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

    order = db.query(Order).filter(Order.order_number == order_id).first()
    if not order:
        raise HTTPException(status_code=404)

    if result_code == "00":
        _mark_order_paid(order, db, background_tasks)
    elif result_code in ["01", "02"]:
        order.status = OrderStatus.failed
        db.commit()

    return {"status": "ok"}


@router.post("/checkout/callback/mayar")
async def mayar_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    body = await request.json()
    order_id = body.get("externalId")
    status = body.get("status")

    order = db.query(Order).filter(Order.order_number == order_id).first()
    if not order:
        raise HTTPException(status_code=404)

    if status in ["PAID", "SETTLED"]:
        _mark_order_paid(order, db, background_tasks)
    elif status in ["FAILED", "EXPIRED"]:
        order.status = OrderStatus.failed
        db.commit()

    return {"status": "ok"}


# ─── Helper ─────────────────────────────────────────────────────────────────

def _mark_order_paid(order: Order, db: Session, background_tasks: BackgroundTasks):
    # Idempotency guard — Duitku may retry webhook
    if order.status == OrderStatus.paid:
        return

    order.status = OrderStatus.paid
    order.paid_at = datetime.utcnow()
    db.commit()

    # Audit log
    try:
        ev.log_order_paid(db, order)
    except Exception:
        pass

    # Increment promo usage only on confirmed payment
    if order.promo_code:
        try:
            promo = db.query(PromoCode).filter(PromoCode.code == order.promo_code).first()
            if promo:
                promo.used_count += 1
                db.commit()
        except Exception:
            pass

    order_id_str = str(order.id)

    # Always schedule via FastAPI background task (non-blocking).
    from app.services.invoice import create_invoice
    background_tasks.add_task(create_invoice, order_id_str)
    try:
        from app.tasks.invoice import create_invoice_task
        create_invoice_task.delay(order_id_str)
    except Exception:
        pass  # Celery not available, background task covers it

    # In-app notification: order paid
    try:
        from app.services.notification import notify_order_paid
        notify_order_paid(db, order)
    except Exception:
        pass

    # Email: order confirmation (background, non-blocking)
    try:
        from app.services.email import send_order_confirmation
        background_tasks.add_task(send_order_confirmation, order)
    except Exception:
        pass

    # Generate product license
    try:
        from app.services.license import generate_license, send_webhook
        from app.services.email import send_license_delivery
        # Find related subscription if any
        sub = None
        if order.type == OrderType.subscription:
            sub = db.query(Subscription).filter(
                Subscription.user_id   == order.user_id,
                Subscription.product_id == order.product_id,
            ).order_by(Subscription.started_at.desc()).first()
        lic = generate_license(db, order, subscription=sub)
        if lic:
            # Email delivery: send token/password/URL to user
            background_tasks.add_task(send_license_delivery, order, lic)
            # Webhook — package.webhook_url takes priority over product
            webhook_url = (
                (order.package.webhook_url if order.package else None)
                or (order.product.webhook_url if order.product else None)
            )
            if webhook_url:
                background_tasks.add_task(
                    send_webhook,
                    webhook_url,
                    "license.created",
                    {
                        "license_key":  lic.license_key,
                        "license_type": lic.license_type,
                        "expires_at":   lic.expires_at.isoformat() if lic.expires_at else None,
                        "order_id":     str(order.id),
                        "package_code": order.package.code if order.package else None,
                        "limits":       (lic.license_metadata or {}).get("limits", {}),
                        "user_email":   order.user.email if order.user else None,
                    }
                )
    except Exception as e:
        logger.error(f"[license] generation failed order={order.id} error={e}")

    # Handle subscription
    if order.type == OrderType.subscription:
        # Check if this is a renewal (subscription already exists)
        existing_sub = db.query(Subscription).filter(
            Subscription.user_id == order.user_id,
            Subscription.product_id == order.product_id,
            Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.past_due]),
        ).first()

        if existing_sub:
            # Package upgrade/downgrade: update package_id if it changed
            if order.package_id and str(existing_sub.package_id) != str(order.package_id):
                existing_sub.package_id = order.package_id
                db.commit()
            # Extend billing via renewal task (covers both renewals and upgrades)
            try:
                from app.tasks.billing import confirm_subscription_renewal
                confirm_subscription_renewal.delay(order_id_str)
            except Exception:
                pass
        else:
            # New subscription
            _create_subscription(order, db)


def _create_subscription(order: Order, db: Session):
    existing = db.query(Subscription).filter(
        Subscription.user_id == order.user_id,
        Subscription.product_id == order.product_id,
        Subscription.status == SubscriptionStatus.active,
    ).first()
    if existing:
        return

    now = datetime.utcnow()

    # Determine cycle — package_price is authoritative, fallback to monthly for legacy orders.
    pkg_price = order.package_price
    if pkg_price and pkg_price.billing_type.value == "yearly":
        cycle        = BillingCycle.yearly
        next_billing = now + timedelta(days=365)
    else:
        cycle        = BillingCycle.monthly
        next_billing = now + timedelta(days=30)

    sub = Subscription(
        id=uuid.uuid4(),
        user_id=order.user_id,
        product_id=order.product_id,
        package_id=order.package_id,
        status=SubscriptionStatus.active,
        billing_cycle=cycle,
        started_at=now,
        next_billing_date=next_billing,
    )
    db.add(sub)
    db.commit()

    try:
        ev.log_subscription_created(db, order, subscription_id=sub.id)
    except Exception:
        pass


@router.post("/{locale}/checkout/{product_id}/request-quote")
async def request_quote(
    request: Request, locale: str, product_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Contact-sales lead capture for BillingType.contact packages.
    Saves a ContactMessage and emails admin.
    """
    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid request"}, status_code=400)

    product = db.query(Product).filter(
        Product.id == product_id, Product.status == ProductStatus.active
    ).first()
    if not product:
        return JSONResponse({"detail": "Product not found"}, status_code=404)

    package_id  = str(body.get("package_id", "")).strip()
    user_message = str(body.get("message", "")).strip()
    package_name = str(body.get("package_name", "")).strip()

    product_name = product.name_id if locale == "id" else product.name_en
    subject = f"[Quote Request] {product_name}" + (f" — {package_name}" if package_name else "")
    full_message = (
        f"Produk: {product_name}\n"
        f"Paket: {package_name or '—'}\n"
        f"User: {current_user.name} ({current_user.email})\n\n"
        f"{user_message or '(tidak ada pesan tambahan)'}"
    )

    from app.models.contact import ContactMessage
    contact = ContactMessage(
        name=current_user.name,
        email=current_user.email,
        subject=subject,
        message=full_message,
        ip_address=request.client.host if request.client else None,
    )
    db.add(contact)
    db.commit()

    # Email admin
    def _send_quote_email():
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            msg = MIMEMultipart()
            msg["From"]    = settings.SMTP_FROM
            msg["To"]      = settings.SMTP_FROM
            msg["Subject"] = subject
            msg.attach(MIMEText(full_message, "plain"))
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as s:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
        except Exception as e:
            logger.error(f"[request-quote] email failed: {e}")

    background_tasks.add_task(_send_quote_email)

    return JSONResponse({"status": "sent"})


@router.post("/checkout/orders/{order_id}/cancel")
async def cancel_order(
    request: Request, order_id: str,
    db: Session = Depends(get_db),
):
    """AJAX — cancel a pending order owned by the logged-in user."""
    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return JSONResponse({"detail": "Order not found"}, status_code=404)

    if str(order.user_id) != str(current_user.id):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    if order.status != OrderStatus.pending:
        return JSONResponse({"detail": "Only pending orders can be cancelled"}, status_code=400)

    order.status = OrderStatus.cancelled
    db.commit()

    try:
        from app.models.order_event import OrderActorType
        ev.log_order_cancelled(db, order, actor_type=OrderActorType.customer, actor_id=current_user.id)
    except Exception:
        pass

    return JSONResponse({"status": "cancelled", "order_id": str(order.id)})
