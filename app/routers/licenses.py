"""
License router — signed download endpoint + dashboard license page.
"""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_login
from app.core.config import settings
from app.core.database import get_db
from app.models.license import LicenseType, ProductLicense

logger = logging.getLogger(__name__)
router = APIRouter(tags=["licenses"])


# ─── Signed Download ──────────────────────────────────────────────────────────

@router.get("/download/{token}")
async def signed_download(token: str, request: Request, db: Session = Depends(get_db)):
    """
    Signed download endpoint — validates token, checks download limit, serves file.
    Token is the license_key of a 'download' type license.
    """
    from app.services.license import verify_download_token
    current_user = get_current_user(request, db)

    lic = verify_download_token(db, token)
    if not lic:
        raise HTTPException(
            status_code=404,
            detail="Link download tidak valid, sudah habis, atau telah dicabut."
        )

    # Ownership check — only the license owner can download
    if current_user and str(lic.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Akses ditolak.")

    # Serve the file
    product = lic.product
    if not product or not product.download_file:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")

    file_path = os.path.join("static", "uploads", "products", "files", product.download_file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File tidak tersedia di server.")

    filename = product.download_file
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


# ─── Dashboard: My Licenses ───────────────────────────────────────────────────

@router.get("/{locale}/dashboard/licenses")
async def dashboard_licenses(
    request: Request,
    locale: str,
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    licenses = db.query(ProductLicense).filter(
        ProductLicense.user_id == current_user.id,
    ).order_by(ProductLicense.created_at.desc()).all()

    from app.main import templates
    return templates.TemplateResponse(
        request, "dashboard/licenses.html",
        {
            "locale":       locale,
            "current_user": current_user,
            "licenses":     licenses,
            "active_page":  "licenses",
        },
    )


@router.get("/{locale}/dashboard/licenses/{license_id}")
async def dashboard_license_detail(
    request: Request,
    locale: str,
    license_id: str,
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    lic = db.query(ProductLicense).filter(
        ProductLicense.id == license_id,
        ProductLicense.user_id == current_user.id,
    ).first()
    if not lic:
        raise HTTPException(status_code=404)

    from app.main import templates
    from app.services.license import generate_signed_download_url
    download_url = generate_signed_download_url(lic) if lic.license_type == LicenseType.download else None

    return templates.TemplateResponse(
        request, "dashboard/license_detail.html",
        {
            "locale":        locale,
            "current_user":  current_user,
            "license":       lic,
            "download_url":  download_url,
            "active_page":   "licenses",
        },
    )
