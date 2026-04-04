import hashlib
import base64
import bcrypt
from itsdangerous import URLSafeTimedSerializer
from app.core.config import settings

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)


def _prepare(plain: str) -> bytes:
    """SHA-256 + base64 to keep input safely under bcrypt's 72-byte limit."""
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)


def create_session_token(data: dict) -> str:
    return serializer.dumps(data)


def verify_session_token(token: str, max_age: int = 86400) -> dict | None:
    try:
        return serializer.loads(token, max_age=max_age)
    except Exception:
        return None


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
