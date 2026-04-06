"""
Security utilities — password hashing and session token management.

Password hashing:
  SHA-256 + base64 pre-hash before bcrypt to avoid the 72-byte bcrypt limit.
  This is the same approach used by Django and Devise.

Session tokens:
  Signed with itsdangerous URLSafeTimedSerializer (SECRET_KEY).
  Default session: 1 day. Remember Me: 30 days.
"""
import base64
import hashlib

import bcrypt
from itsdangerous import URLSafeTimedSerializer

from app.core.config import settings

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)


def _prepare(plain: str) -> bytes:
    """SHA-256 + base64 to keep input safely under bcrypt's 72-byte limit."""
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)


SESSION_SHORT = 86400        # 1 day  (default)
SESSION_LONG  = 86400 * 30   # 30 days (remember me)


def create_session_token(data: dict) -> str:
    return serializer.dumps(data)


def verify_session_token(token: str, max_age: int = SESSION_LONG) -> dict | None:
    """Verify token. max_age must be >= the longest possible session duration."""
    try:
        return serializer.loads(token, max_age=max_age)
    except Exception:
        return None


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
