"""
License service — generate, validate, revoke, and deliver product licenses.

License types:
  token      → TWJ-XXXX-XXXX-XXXX-XXXX  (API-validated by external apps)
  password   → random strong password    (file encryption / ZIP)
  credential → username + password       (service access)
  download   → signed URL token          (ebook, template, file)
  none       → no license generated
"""
import hashlib
import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.license import LicenseActivation, LicenseType, ProductLicense
from app.models.order import Order
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)

# ── Token formats ─────────────────────────────────────────────────────────────

def _generate_license_token() -> str:
    """Generate a license key: TWJ-XXXX-XXXX-XXXX-XXXX (uppercase alphanum)."""
    chars = string.ascii_uppercase + string.digits
    segments = ["".join(secrets.choice(chars) for _ in range(4)) for _ in range(4)]
    return "TWJ-" + "-".join(segments)


def _generate_password(length: int = 16) -> str:
    """Generate a strong random password with mixed chars."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Guarantee at least one of each category
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    pwd += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


def _generate_username(user_name: str, product_slug: str) -> str:
    """Generate a username: first_part_of_name + _ + product_slug prefix."""
    base = (user_name or "user").split()[0].lower()
    base = "".join(c for c in base if c.isalnum())[:12]
    suffix = secrets.token_hex(3)
    return f"{base}_{product_slug[:8]}_{suffix}"


def _generate_download_token() -> str:
    """Cryptographically secure 48-char token for signed download URLs."""
    return secrets.token_urlsafe(36)


def _license_expiry(order: Order, product, subscription: Subscription | None) -> datetime | None:
    """
    Calculate license expiry date:
    1. If product has license_duration_days → use that
    2. If subscription → follow next_billing_date
    3. If one_time → lifetime (None)
    """
    if product.license_duration_days:
        return datetime.utcnow() + timedelta(days=product.license_duration_days)
    if subscription and subscription.next_billing_date:
        return subscription.next_billing_date
    if order.type.value == "subscription":
        # Fallback: 30 days monthly, 365 yearly
        from app.models.subscription import BillingCycle
        if subscription and subscription.billing_cycle == BillingCycle.yearly:
            return datetime.utcnow() + timedelta(days=365)
        return datetime.utcnow() + timedelta(days=30)
    return None  # one_time = lifetime


# ── Main generation ───────────────────────────────────────────────────────────

def generate_license(
    db: Session,
    order: Order,
    subscription: Subscription | None = None,
) -> ProductLicense | None:
    """
    Generate and persist a ProductLicense after a successful order.
    Returns None if product has license_type = 'none'.
    """
    product = order.product
    if not product:
        logger.warning(f"[license] order {order.id} has no product")
        return None

    ltype = (product.license_type or "none").lower()
    if ltype == "none":
        return None

    expires_at = _license_expiry(order, product, subscription)
    grace_until = (expires_at + timedelta(days=3)) if expires_at else None

    license_key      = None
    license_password = None
    license_username = None
    access_url       = product.access_url

    if ltype == LicenseType.token:
        license_key = _generate_license_token()

    elif ltype == LicenseType.password:
        license_password = _generate_password()

    elif ltype == LicenseType.credential:
        license_username = _generate_username(order.user.name or "user", product.slug)
        license_password = _generate_password()

    elif ltype == LicenseType.download:
        license_key = _generate_download_token()  # used as signed URL token

    lic = ProductLicense(
        id               = uuid.uuid4(),
        order_id         = order.id,
        user_id          = order.user_id,
        product_id       = order.product_id,
        subscription_id  = subscription.id if subscription else None,
        license_type     = ltype,
        license_key      = license_key,
        license_password = license_password,
        license_username = license_username,
        access_url       = access_url,
        expires_at       = expires_at,
        grace_until      = grace_until,
        max_activations  = product.max_activations or 1,
        max_downloads    = 5,
        is_active        = True,
        license_metadata = {},
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    logger.info(f"[license] generated type={ltype} id={lic.id} order={order.id}")
    return lic


# ── Renewal (subscription renews) ────────────────────────────────────────────

def renew_license(db: Session, license: ProductLicense, subscription: Subscription) -> ProductLicense:
    """
    On subscription renewal:
    - Extend expires_at + grace_until
    - For token type: keep same key (don't break existing integrations)
    - Reset reminder flags
    """
    product = license.product
    new_expires = _license_expiry(license.order, product, subscription)
    license.expires_at      = new_expires
    license.grace_until     = (new_expires + timedelta(days=3)) if new_expires else None
    license.is_active       = True
    license.revoked_at      = None
    license.revoked_reason  = None
    license.reminded_7d     = False
    license.reminded_3d     = False
    license.reminded_expired = False
    db.commit()
    db.refresh(license)
    logger.info(f"[license] renewed id={license.id} new_expires={new_expires}")
    return license


# ── Revoke ────────────────────────────────────────────────────────────────────

def revoke_license(db: Session, license: ProductLicense, reason: str = "") -> ProductLicense:
    license.is_active      = False
    license.revoked_at     = datetime.utcnow()
    license.revoked_reason = reason
    db.commit()
    logger.info(f"[license] revoked id={license.id} reason={reason}")
    return license


# ── Token validation (called by external apps) ────────────────────────────────

def validate_token(db: Session, token: str, device_id: str = "", ip: str = "") -> dict:
    """
    Validate a license token from an external application.
    Updates activated_count and records activation.
    Returns a dict with validation result.
    """
    lic = db.query(ProductLicense).filter(
        ProductLicense.license_key == token,
        ProductLicense.license_type == LicenseType.token,
    ).first()

    if not lic:
        return {"valid": False, "reason": "token_not_found"}
    if not lic.is_active:
        return {"valid": False, "reason": "token_revoked"}
    if lic.is_expired and not lic.is_in_grace:
        return {"valid": False, "reason": "token_expired", "expired_at": lic.expires_at.isoformat() if lic.expires_at else None}

    # Check max activations
    active_activations = db.query(LicenseActivation).filter(
        LicenseActivation.license_id == lic.id,
        LicenseActivation.is_active == True,
    ).count()

    # Check if this device already activated
    existing = None
    if device_id:
        existing = db.query(LicenseActivation).filter(
            LicenseActivation.license_id == lic.id,
            LicenseActivation.device_id  == device_id,
            LicenseActivation.is_active  == True,
        ).first()

    if not existing:
        if active_activations >= lic.max_activations:
            return {
                "valid":  False,
                "reason": "max_activations_reached",
                "max":    lic.max_activations,
                "current": active_activations,
            }
        # Record new activation
        act = LicenseActivation(
            id           = uuid.uuid4(),
            license_id   = lic.id,
            device_id    = device_id or None,
            ip_address   = ip or None,
            activated_at = datetime.utcnow(),
            last_seen_at = datetime.utcnow(),
        )
        db.add(act)
        lic.activated_count += 1
        db.commit()
    else:
        existing.last_seen_at = datetime.utcnow()
        db.commit()

    return {
        "valid":        True,
        "license_id":   str(lic.id),
        "product_id":   str(lic.product_id),
        "user_id":      str(lic.user_id),
        "license_type": lic.license_type,
        "expires_at":   lic.expires_at.isoformat() if lic.expires_at else None,
        "is_lifetime":  lic.expires_at is None,
        "days_left":    lic.days_until_expiry,
        "in_grace":     lic.is_in_grace,
        "access_url":   lic.access_url,
    }


# ── Signed download URL ───────────────────────────────────────────────────────

def generate_signed_download_url(license: ProductLicense) -> str:
    """Return a signed download URL using the license_key as token."""
    return f"{settings.BASE_URL}/download/{license.license_key}"


def verify_download_token(db: Session, token: str) -> ProductLicense | None:
    """Verify a signed download token and increment download count."""
    lic = db.query(ProductLicense).filter(
        ProductLicense.license_key   == token,
        ProductLicense.license_type  == LicenseType.download,
        ProductLicense.is_active     == True,
    ).first()
    if not lic:
        return None
    if lic.download_count >= lic.max_downloads:
        return None
    lic.download_count      += 1
    lic.last_downloaded_at   = datetime.utcnow()
    db.commit()
    return lic


# ── Webhook notification ──────────────────────────────────────────────────────

async def send_webhook(url: str, event: str, payload: dict) -> None:
    """POST event notification to product's webhook_url."""
    if not url:
        return
    body = {"event": event, "timestamp": datetime.utcnow().isoformat(), **payload}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=body)
            logger.info(f"[webhook] event={event} url={url} status={resp.status_code}")
    except Exception as e:
        logger.warning(f"[webhook] failed event={event} url={url} error={e}")
