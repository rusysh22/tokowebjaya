"""
Landing router — public-facing pages and auth page routes.

Routes:
  GET  /                        — Auto-detect locale and redirect
  GET  /{locale}/               — Home / landing page
  GET  /{locale}/about          — About page
  GET  /{locale}/solutions      — Solutions page
  GET  /{locale}/contact        — Contact page
  GET  /{locale}/login          — Login page (Google + Email tabs)
  GET  /{locale}/register       — Register page
  GET  /{locale}/verify-email   — Email verification OTP page
  GET  /{locale}/forgot-password — Forgot password page
  GET  /{locale}/reset-password — Reset password OTP + new password page
"""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.contact import ContactMessage
from app.models.product import Product, ProductStatus

router = APIRouter(tags=["landing"])


@router.get("/")
async def root(request: Request):
    locale = _detect_locale(request)
    return RedirectResponse(url=f"/{locale}/")


@router.get("/{locale}/")
async def landing(request: Request, locale: str, db: Session = Depends(get_db)):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/")

    from app.main import templates
    current_user = get_current_user(request, db)

    featured = (
        db.query(Product)
        .filter(Product.status == ProductStatus.active, Product.is_featured == True)
        .order_by(Product.sort_order)
        .limit(6)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "landing/index.html",
        {
            "locale": locale,
            "current_user": current_user,
            "active_page": "home",
            "featured_products": featured,
        },
    )


@router.get("/{locale}/about")
async def about(request: Request, locale: str, db: Session = Depends(get_db)):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/about")
    from app.main import templates
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        request, "landing/about.html",
        {"locale": locale, "current_user": current_user, "active_page": "about"},
    )


@router.get("/{locale}/solutions")
async def solutions(request: Request, locale: str, db: Session = Depends(get_db)):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/solutions")
    from app.main import templates
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        request, "landing/solutions.html",
        {"locale": locale, "current_user": current_user, "active_page": "solutions"},
    )


@router.get("/{locale}/contact")
async def contact(
    request: Request, locale: str,
    success: str = None, error: str = None,
    db: Session = Depends(get_db),
):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/contact")
    from app.main import templates
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        request, "landing/contact.html",
        {"locale": locale, "current_user": current_user, "active_page": "contact",
         "success": success, "error": error},
    )


@router.post("/{locale}/contact")
async def contact_submit(
    request: Request,
    locale: str,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(default=""),
    message: str = Form(...),
    db: Session = Depends(get_db),
):
    if locale not in settings.SUPPORTED_LOCALES:
        locale = settings.DEFAULT_LOCALE

    # Basic validation
    name    = name.strip()[:255]
    email   = email.strip().lower()[:255]
    subject = subject.strip()[:500]
    message = message.strip()

    if not name or not email or not message:
        return RedirectResponse(
            url=f"/{locale}/contact?error=missing_fields", status_code=302
        )

    if len(message) < 10:
        return RedirectResponse(
            url=f"/{locale}/contact?error=message_too_short", status_code=302
        )

    # Get client IP
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")

    # Save to DB
    msg = ContactMessage(
        id=uuid.uuid4(),
        name=name,
        email=email,
        subject=subject,
        message=message,
        ip_address=ip[:64] if ip else None,
    )
    db.add(msg)
    db.commit()

    # Send notifications in background (non-blocking)
    from app.services.email import send_contact_notification, send_contact_autoreply
    if settings.ADMIN_EMAIL:
        background_tasks.add_task(
            send_contact_notification, name, email, subject, message, settings.ADMIN_EMAIL
        )
    background_tasks.add_task(send_contact_autoreply, name, email, locale)

    return RedirectResponse(url=f"/{locale}/contact?success=1", status_code=302)


@router.get("/{locale}/login")
async def login_page(
    request: Request, locale: str,
    error: str = None, tab: str = "google", email: str = None,
    db: Session = Depends(get_db),
):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/login")
    from app.main import templates
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url=f"/{locale}/dashboard")
    return templates.TemplateResponse(
        request, "auth/login.html",
        {"locale": locale, "current_user": None, "error": error, "tab": tab, "prefill_email": email},
    )


@router.get("/{locale}/register")
async def register_page(
    request: Request, locale: str,
    error: str = None, email: str = None, name: str = None,
    db: Session = Depends(get_db),
):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/register")
    from app.main import templates
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url=f"/{locale}/dashboard")
    return templates.TemplateResponse(
        request, "auth/register.html",
        {"locale": locale, "current_user": None, "error": error, "prefill_email": email, "prefill_name": name},
    )


@router.get("/{locale}/verify-email")
async def verify_email_page(
    request: Request, locale: str,
    email: str = None, error: str = None, resent: str = None,
    db: Session = Depends(get_db),
):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/verify-email")
    from app.main import templates
    return templates.TemplateResponse(
        request, "auth/verify_email.html",
        {"locale": locale, "current_user": None, "email": email, "error": error, "resent": resent},
    )


@router.get("/{locale}/forgot-password")
async def forgot_password_page(
    request: Request, locale: str,
    error: str = None,
    db: Session = Depends(get_db),
):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/forgot-password")
    from app.main import templates
    return templates.TemplateResponse(
        request, "auth/forgot_password.html",
        {"locale": locale, "current_user": None, "error": error},
    )


@router.get("/{locale}/reset-password")
async def reset_password_page(
    request: Request, locale: str,
    email: str = None, error: str = None,
    db: Session = Depends(get_db),
):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/reset-password")
    from app.main import templates
    return templates.TemplateResponse(
        request, "auth/reset_password.html",
        {"locale": locale, "current_user": None, "email": email, "error": error},
    )


def _detect_locale(request: Request) -> str:
    accept = request.headers.get("accept-language", "")
    if "id" in accept:
        return "id"
    return "id"
