"""
Notifications router — in-app notification pages and AJAX endpoints.

Routes:
  GET  /{locale}/dashboard/notifications            — Notification list (marks all read on open)
  POST /{locale}/dashboard/notifications/{id}/read  — Mark single notification read
  GET  /api/notifications/unread-count              — AJAX: unread count for navbar badge
"""
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.notification import Notification

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])


def _require_user(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        path = request.url.path
        for loc in ["id", "en"]:
            if path.startswith(f"/{loc}/"):
                return RedirectResponse(url=f"/{loc}/login"), None
        return RedirectResponse(url="/id/login"), None
    return None, user


@router.get("/{locale}/dashboard/notifications")
async def notifications_page(request: Request, locale: str, db: Session = Depends(get_db)):
    if locale not in settings.SUPPORTED_LOCALES:
        return RedirectResponse(url=f"/{settings.DEFAULT_LOCALE}/dashboard/notifications")

    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(desc(Notification.created_at))
        .limit(50)
        .all()
    )

    # Mark all as read when page opened
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()

    from app.main import templates
    return templates.TemplateResponse(
        request, "dashboard/notifications.html",
        {"locale": locale, "current_user": user, "notifications": notifications, "active_page": "notifications"},
    )


@router.post("/{locale}/dashboard/notifications/{notif_id}/read")
async def mark_read(request: Request, locale: str, notif_id: str, db: Session = Depends(get_db)):
    redirect, user = _require_user(request, db)
    if redirect:
        return redirect

    notif = db.query(Notification).filter(
        Notification.id == notif_id, Notification.user_id == user.id
    ).first()
    if notif:
        notif.is_read = True
        db.commit()
    return JSONResponse({"ok": True})


@router.get("/api/notifications/unread-count")
async def unread_count(request: Request, db: Session = Depends(get_db)):
    """AJAX endpoint — returns unread notification count for current user."""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"count": 0})
    count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).count()
    return JSONResponse({"count": count})
