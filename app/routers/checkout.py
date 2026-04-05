"""
Checkout router — handles the full purchase flow:
  1. Review page  GET  /{locale}/checkout/{product_id}
  2. Validate promo (AJAX)      POST /checkout/promo/validate
  3. Create payment (AJAX/JSON) POST /{locale}/checkout/{product_id}/create-payment
  4. Legacy form-based process  POST /{locale}/checkout/{product_id}/process
  5. Return page after redirect GET  /{locale}/checkout/return/{order_id}
  6. Payment status polling     GET  /checkout/status/{order_id}
  7. Duitku webhook             POST /checkout/callback/duitku
  8. Mayar webhook              POST /checkout/callback/mayar

Pricing contract (IDR):
  base_amount  = product price (excl. VAT)
  discount     = promo discount applied to base_amount
  subtotal     = base_amount - discount
  vat          = subtotal * VAT_RATE (11% PPN for IDR)
  final_amount = subtotal + vat   ← this is what Duitku charges
"""
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.order import Order, OrderStatus, OrderType, PaymentGateway
from app.models.product import Product, ProductStatus
from app.models.promo import PromoCode
from app.models.subscription import BillingCycle, Subscription, SubscriptionStatus
from app.services.payment import duitku, generate_order_number, mayar

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

    if not code:
        return JSONResponse({"valid": False, "reason": "empty"})

    promo, reason = _resolve_promo(code, base_idr, db)
    if not promo:
        reason_msg = {
            "not_found":     "Kode promo tidak ditemukan.",
            "expired":       "Kode promo sudah kadaluarsa.",
            "not_started":   "Kode promo belum aktif.",
            "used_up":       "Kode promo sudah habis digunakan.",
            "below_minimum": f"Minimum pembelian untuk promo ini adalah Rp {float(promo.min_amount or 0):,.0f}." if promo else "Minimum pembelian tidak terpenuhi.",
            "inactive":      "Kode promo tidak aktif.",
        }.get(reason, "Kode promo tidak valid.")
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
    type: str = "one_time", cycle: str = "monthly",
    currency: str = "",
    db: Session = Depends(get_db),
):
    import uuid as _uuid
    # Guard against non-UUID path segments (e.g. /checkout/failed hitting this route)
    try:
        _uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/catalog")

    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url=f"/{locale}/login?next=/{locale}/checkout/{product_id}")

    product = db.query(Product).filter(
        Product.id == product_id, Product.status == ProductStatus.active
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Resolve currency
    if not currency or currency not in settings.SUPPORTED_CURRENCIES:
        currency = settings.DEFAULT_CURRENCY

    # Determine price (always in IDR base)
    amount_idr = None
    if type == "one_time" and product.price_otf:
        amount_idr = float(product.price_otf)
    elif type == "subscription":
        if cycle == "yearly" and product.price_yearly:
            amount_idr = float(product.price_yearly)
        elif product.price_monthly:
            amount_idr = float(product.price_monthly)

    if not amount_idr:
        raise HTTPException(status_code=400, detail="Invalid pricing configuration")

    from app.core.currency import get_display_prices
    pricing = get_display_prices(amount_idr, currency, include_vat=True)

    # Fetch active promo codes (shown as dropdown suggestions)
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
            "order_type": type,
            "billing_cycle": cycle,
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
    """AJAX endpoint — returns JSON with payment_url for Duitku Pop.js."""

    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    order_type    = body.get("order_type", "one_time")
    billing_cycle = body.get("billing_cycle", "monthly")
    promo_code    = str(body.get("promo_code", "")).strip().upper()

    product = db.query(Product).filter(
        Product.id == product_id, Product.status == ProductStatus.active
    ).first()
    if not product:
        return JSONResponse({"detail": "Product not found"}, status_code=404)

    # Base price (IDR, excl. VAT)
    base_amount = None
    if order_type == "one_time":
        base_amount = float(product.price_otf) if product.price_otf else None
    elif order_type == "subscription":
        base_amount = float(product.price_yearly) if billing_cycle == "yearly" and product.price_yearly else (
            float(product.price_monthly) if product.price_monthly else None
        )

    if not base_amount:
        return JSONResponse({"detail": "Invalid amount"}, status_code=400)

    # Resolve promo
    promo, promo_error = _resolve_promo(promo_code, base_amount, db)
    if promo_code and not promo:
        return JSONResponse({"detail": f"Promo tidak valid: {promo_error}"}, status_code=400)

    # Calculate final amount (base - discount + VAT)
    breakdown = _calc_final_amount(base_amount, promo)
    charge_amount = int(breakdown["final"])   # IDR integer sent to Duitku
    logger.info(
        "Checkout breakdown — base=%.0f discount=%.0f subtotal=%.0f vat=%.0f final=%d",
        breakdown["base"], breakdown["discount"], breakdown["subtotal"],
        breakdown["vat_amount"], charge_amount,
    )

    order_number = generate_order_number()
    order = Order(
        id=uuid.uuid4(),
        order_number=order_number,
        user_id=current_user.id,
        product_id=product.id,
        type=order_type,
        amount=base_amount,
        discount_amount=breakdown["discount"],
        final_amount=breakdown["final"],
        promo_code=promo.code if promo else None,
        status=OrderStatus.pending,
        payment_gateway=PaymentGateway.duitku,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return_url = f"{settings.BASE_URL}/{locale}/checkout/return/{order.id}"
    product_name = product.name_id if locale == "id" else product.name_en

    try:
        result = await duitku.create_payment(
            order_number=order_number,
            amount=charge_amount,          # ← final amount incl. VAT, after discount
            product_name=product_name,
            customer_name=current_user.name,
            customer_email=current_user.email,
            return_url=return_url,
        )
        payment_url = result.get("paymentUrl") or result.get("payment_url")
        reference = result.get("reference") or result.get("merchantOrderId")

        order.gateway_payment_url = payment_url
        order.gateway_reference = reference
        db.commit()

        # Increment promo used_count
        if promo:
            promo.used_count += 1
            db.commit()

        return JSONResponse({
            "payment_url":    payment_url,
            "reference":      reference,
            "order_id":       str(order.id),
            "order_number":   order_number,
            "final_amount":   charge_amount,
            "discount":       breakdown["discount"],
        })

    except Exception as e:
        order.status = OrderStatus.failed
        db.commit()
        logger.error(f"[create-payment] {e}")
        return JSONResponse({"detail": "Payment gateway error. Please try again."}, status_code=502)


@router.post("/{locale}/checkout/{product_id}/process")
async def checkout_process(
    request: Request, locale: str, product_id: str,
    background_tasks: BackgroundTasks,
    order_type: str = Form("one_time"),
    billing_cycle: str = Form("monthly"),
    gateway: str = Form("duitku"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url=f"/{locale}/login")

    product = db.query(Product).filter(
        Product.id == product_id, Product.status == ProductStatus.active
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Determine amount
    amount = None
    if order_type == "one_time":
        amount = float(product.price_otf) if product.price_otf else None
    elif order_type == "subscription":
        if billing_cycle == "yearly":
            amount = float(product.price_yearly) if product.price_yearly else None
        else:
            amount = float(product.price_monthly) if product.price_monthly else None

    if not amount:
        raise HTTPException(status_code=400, detail="Invalid amount")

    order_number = generate_order_number()

    order = Order(
        id=uuid.uuid4(),
        order_number=order_number,
        user_id=current_user.id,
        product_id=product.id,
        type=order_type,
        amount=amount,
        status=OrderStatus.pending,
        payment_gateway=PaymentGateway(gateway),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return_url = f"{settings.BASE_URL}/{locale}/checkout/return/{order.id}"
    product_name = product.name_id if locale == "id" else product.name_en

    try:
        if gateway == "duitku":
            result = await duitku.create_payment(
                order_number=order_number,
                amount=int(amount),
                product_name=product_name,
                customer_name=current_user.name,
                customer_email=current_user.email,
                return_url=return_url,
            )
            logger.debug(f"[duitku] response: {result}")
            payment_url = result.get("paymentUrl") or result.get("payment_url")
            reference = result.get("reference") or result.get("merchantOrderId")
        else:
            result = await mayar.create_payment(
                order_number=order_number,
                amount=int(amount),
                product_name=product_name,
                customer_name=current_user.name,
                customer_email=current_user.email,
                return_url=return_url,
            )
            payment_url = result.get("data", {}).get("link") or result.get("paymentLink")
            reference = result.get("data", {}).get("id") or order_number

        order.gateway_payment_url = payment_url
        order.gateway_reference = reference
        db.commit()

        if payment_url:
            return RedirectResponse(url=payment_url, status_code=303)

    except Exception as e:
        logger.error(f"[checkout/process] {e}")
        order.status = OrderStatus.failed
        db.commit()
        return RedirectResponse(url=f"/{locale}/checkout/failed?order={order.id}", status_code=303)

    return RedirectResponse(url=f"/{locale}/checkout/pending?order={order.id}", status_code=303)


@router.get("/{locale}/checkout/return/{order_id}")
async def checkout_return(
    request: Request, locale: str, order_id: str,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404)
    from app.main import templates
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        request, "checkout/return.html",
        {"locale": locale, "current_user": current_user, "order": order},
    )


@router.get("/checkout/status/{order_id}")
async def checkout_status(order_id: str, db: Session = Depends(get_db)):
    """AJAX endpoint — returns current order status."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return JSONResponse({"status": "not_found"}, status_code=404)
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
    order.status = OrderStatus.paid
    order.paid_at = datetime.utcnow()
    db.commit()

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

    # Handle subscription
    if order.type == OrderType.subscription:
        # Check if this is a renewal (subscription already exists)
        existing_sub = db.query(Subscription).filter(
            Subscription.user_id == order.user_id,
            Subscription.product_id == order.product_id,
            Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.past_due]),
        ).first()

        if existing_sub:
            # Renewal — confirm via Celery billing task
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
    # Determine cycle from amount comparison
    product = order.product
    if product and product.price_yearly and float(order.amount) == float(product.price_yearly):
        cycle = BillingCycle.yearly
        next_billing = now + timedelta(days=365)
    else:
        cycle = BillingCycle.monthly
        next_billing = now + timedelta(days=30)

    sub = Subscription(
        id=uuid.uuid4(),
        user_id=order.user_id,
        product_id=order.product_id,
        status=SubscriptionStatus.active,
        billing_cycle=cycle,
        started_at=now,
        next_billing_date=next_billing,
    )
    db.add(sub)
    db.commit()
