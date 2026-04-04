"""
OTP service using Redis.
- 6-digit numeric OTP
- TTL 10 minutes
- Max 5 attempts before lockout
- Separate namespaces: verify_email, reset_password
"""
import secrets
import redis
from app.core.config import settings

_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def _key(namespace: str, email: str) -> str:
    return f"otp:{namespace}:{email.lower()}"


def _attempts_key(namespace: str, email: str) -> str:
    return f"otp_attempts:{namespace}:{email.lower()}"


OTP_TTL = 600       # 10 minutes
MAX_ATTEMPTS = 5


def generate_otp(namespace: str, email: str) -> str:
    """Generate and store a 6-digit OTP. Returns the OTP string."""
    r = _get_redis()
    otp = f"{secrets.randbelow(1_000_000):06d}"
    r.setex(_key(namespace, email), OTP_TTL, otp)
    # Reset attempt counter on new OTP
    r.delete(_attempts_key(namespace, email))
    return otp


def verify_otp(namespace: str, email: str, code: str) -> tuple[bool, str]:
    """
    Verify OTP. Returns (ok, reason).
    reason: 'ok' | 'expired' | 'invalid' | 'locked'
    """
    r = _get_redis()
    attempts_k = _attempts_key(namespace, email)
    attempts = int(r.get(attempts_k) or 0)

    if attempts >= MAX_ATTEMPTS:
        return False, "locked"

    stored = r.get(_key(namespace, email))
    if stored is None:
        return False, "expired"

    if stored != code.strip():
        r.incr(attempts_k)
        r.expire(attempts_k, OTP_TTL)
        return False, "invalid"

    # Valid — consume it
    r.delete(_key(namespace, email))
    r.delete(attempts_k)
    return True, "ok"


def delete_otp(namespace: str, email: str) -> None:
    r = _get_redis()
    r.delete(_key(namespace, email))
    r.delete(_attempts_key(namespace, email))
