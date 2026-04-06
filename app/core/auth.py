"""
Auth helpers — session-based authentication.

  get_current_user(request, db)  — Returns User or None (no redirect, no exception)
  require_admin(request, db)     — Returns User or raises 403 if not admin
"""
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import verify_session_token
from app.models.user import User, UserRole


def get_current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get("session")
    if not token:
        return None
    data = verify_session_token(token)
    if not data:
        return None
    user = db.query(User).filter(User.id == data.get("user_id")).first()
    if not user or user.status.value == "banned":
        return None
    return user


def require_login(request: Request, db: Session) -> User:
    user = get_current_user(request, db)
    if not user:
        locale = _get_locale_from_path(request.url.path)
        next_url = str(request.url.path)
        if request.url.query:
            next_url += f"?{request.url.query}"
        from urllib.parse import quote
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": f"/{locale}/login?next={quote(next_url)}"},
        )
    return user


def require_admin(request: Request, db: Session) -> User:
    user = require_login(request, db)
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def _get_locale_from_path(path: str) -> str:
    for locale in ["id", "en"]:
        if path.startswith(f"/{locale}/") or path == f"/{locale}":
            return locale
    return "id"
