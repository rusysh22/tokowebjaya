from fastapi import APIRouter, Request, Depends, HTTPException, Form, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from app.core.config import settings
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.product import Product, ProductStatus, PricingModel
from app.models.order import Order, OrderType, OrderStatus, PaymentGateway
from app.models.invoice import Invoice, InvoiceStatus
from app.models.subscription import Subscription, SubscriptionStatus, BillingCycle
from app.services.payment import duitku, mayar, generate_order_number

router = APIRouter(tags=["checkout"])


def _locale(path: str) -> str:
    for loc in ["id", "en"]:
        if path.startswith(f"/{loc}/"):
            return loc
    return "id"


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
        },
    )


@router.post("/{locale}/checkout/{product_id}/create-payment")
async def checkout_create_payment(
    request: Request, locale: str, product_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """AJAX endpoint — returns JSON with payment_url for Duitku Pop.js."""
    from fastapi.responses import JSONResponse

    current_user = get_current_user(request, db)
    if not current_user:
        return JSONResponse({"detail": "Login required"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    order_type = body.get("order_type", "one_time")
    billing_cycle = body.get("billing_cycle", "monthly")

    product = db.query(Product).filter(
        Product.id == product_id, Product.status == ProductStatus.active
    ).first()
    if not product:
        return JSONResponse({"detail": "Product not found"}, status_code=404)

    amount = None
    if order_type == "one_time":
        amount = float(product.price_otf) if product.price_otf else None
    elif order_type == "subscription":
        amount = float(product.price_yearly) if billing_cycle == "yearly" and product.price_yearly else (
            float(product.price_monthly) if product.price_monthly else None
        )

    if not amount:
        return JSONResponse({"detail": "Invalid amount"}, status_code=400)

    order_number = generate_order_number()
    order = Order(
        id=uuid.uuid4(),
        order_number=order_number,
        user_id=current_user.id,
        product_id=product.id,
        type=order_type,
        amount=amount,
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
            amount=int(amount),
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

        return JSONResponse({
            "payment_url": payment_url,
            "reference": reference,
            "order_id": str(order.id),
            "order_number": order_number,
        })

    except Exception as e:
        order.status = OrderStatus.failed
        db.commit()
        import logging
        logging.getLogger("checkout").error(f"[create-payment] error: {e}")
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
            import logging; logging.getLogger("checkout").warning(f"[duitku] response: {result}")
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
        import logging; logging.getLogger("checkout").error(f"[checkout] payment error: {e}")
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
    from fastapi.responses import JSONResponse
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

    import logging
    logging.getLogger("checkout").warning(f"[duitku callback] data={data}")

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
