from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jinja2 import Environment

from app.core.config import settings
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.product import Product, ProductStatus

router = APIRouter(tags=["landing"])


def _templates(request: Request) -> Jinja2Templates:
    from app.main import templates
    return templates


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
async def contact(request: Request, locale: str, db: Session = Depends(get_db)):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/contact")
    from app.main import templates
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        request, "landing/contact.html",
        {"locale": locale, "current_user": current_user, "active_page": "contact"},
    )


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
