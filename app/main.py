from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from jinja2 import FileSystemLoader, Environment
from datetime import datetime
import uuid as _uuid
import logging
import os

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.i18n import get_locale, t
from app.core.currency import format_price, get_display_prices, add_vat, get_vat_rate
from app.core.middleware import SecurityHeadersMiddleware, RateLimitMiddleware
from app.models import license as _license_models  # noqa: F401 — register ORM models


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(f"{settings.UPLOAD_DIR}/products/images", exist_ok=True)
    os.makedirs(f"{settings.UPLOAD_DIR}/products/videos", exist_ok=True)
    os.makedirs(f"{settings.UPLOAD_DIR}/products/files", exist_ok=True)
    os.makedirs(f"{settings.UPLOAD_DIR}/invoices", exist_ok=True)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs" if settings.APP_ENV == "development" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Middleware (order matters: outermost first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="twj_session",
    max_age=86400 * 7,
    https_only=settings.APP_ENV == "production",
    same_site="lax",
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 with global helpers
jinja_env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
jinja_env.globals["t"] = t
jinja_env.globals["now"] = datetime.utcnow
jinja_env.globals["settings"] = settings
jinja_env.globals["format_price"] = format_price
jinja_env.globals["get_display_prices"] = get_display_prices
jinja_env.globals["get_vat_rate"] = get_vat_rate
templates = Jinja2Templates(env=jinja_env)

# Register routers
from app.routers import auth, landing, catalog, admin, checkout, dashboard, api_v1, notifications, appointments, licenses  # noqa: E402
app.include_router(auth.router)
app.include_router(landing.router)
app.include_router(catalog.router)
app.include_router(admin.router)
app.include_router(checkout.router)
app.include_router(dashboard.router)
app.include_router(api_v1.router)
app.include_router(notifications.router)
app.include_router(appointments.router)
app.include_router(licenses.router)


def _get_locale_from_request(request: Request) -> str:
    path = request.url.path
    for loc in ["id", "en"]:
        if path.startswith(f"/{loc}/") or path == f"/{loc}":
            return loc
    return "id"


def _render_error(request: Request, template: str, context: dict, status_code: int):
    from starlette.responses import HTMLResponse
    tmpl = jinja_env.get_template(template)
    context.setdefault("request", request)
    html = tmpl.render(**context)
    return HTMLResponse(content=html, status_code=status_code)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    locale = _get_locale_from_request(request)
    if exc.status_code == 404:
        return _render_error(request, "errors/404.html",
                             {"locale": locale, "current_user": None}, 404)
    if exc.status_code == 500:
        error_id = str(_uuid.uuid4())[:8].upper()
        logger.error(f"[500] error_id={error_id} path={request.url.path}")
        return _render_error(request, "errors/500.html",
                             {"locale": locale, "current_user": None, "error_id": error_id}, 500)
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    locale = _get_locale_from_request(request)
    error_id = str(_uuid.uuid4())[:8].upper()
    logger.exception(f"[unhandled] error_id={error_id} path={request.url.path}: {exc}")
    return _render_error(request, "errors/500.html",
                         {"locale": locale, "current_user": None, "error_id": error_id}, 500)


@app.get("/health")
async def health():
    from app.core.database import SessionLocal
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "db": "ok" if db_ok else "error",
    }


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /id/admin\n"
        "Disallow: /en/admin\n"
        "Disallow: /id/dashboard\n"
        "Disallow: /en/dashboard\n"
        "Disallow: /auth/\n"
        "Disallow: /api/\n"
        "Disallow: /checkout/callback/\n"
        "Disallow: /checkout/status/\n"
        f"Sitemap: {settings.BASE_URL}/sitemap.xml\n"
    )
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    from app.core.database import SessionLocal
    from app.models.product import Product, ProductStatus

    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.status == ProductStatus.active).all()
    finally:
        db.close()

    base = settings.BASE_URL
    now = datetime.utcnow().strftime("%Y-%m-%d")

    static_urls = [
        ("", "1.0", "daily"),
        ("/id/", "1.0", "daily"),
        ("/en/", "1.0", "daily"),
        ("/id/catalog", "0.9", "daily"),
        ("/en/catalog", "0.9", "daily"),
        ("/id/about", "0.7", "monthly"),
        ("/en/about", "0.7", "monthly"),
        ("/id/contact", "0.7", "monthly"),
        ("/en/contact", "0.7", "monthly"),
        ("/id/solutions", "0.7", "monthly"),
        ("/en/solutions", "0.7", "monthly"),
    ]

    urls = ""
    for path, priority, freq in static_urls:
        urls += f"""  <url>
    <loc>{base}{path}</loc>
    <lastmod>{now}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
  </url>\n"""

    for p in products:
        for locale in ["id", "en"]:
            urls += f"""  <url>
    <loc>{base}/{locale}/product/{p.slug}</loc>
    <lastmod>{p.updated_at.strftime('%Y-%m-%d') if p.updated_at else now}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>\n"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}</urlset>"""

    return Response(content=xml, media_type="application/xml")
