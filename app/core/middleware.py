"""
Production middleware:
- Security headers
- Rate limiting (Redis sliding window, per IP)
"""
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis as _redis
        from app.core.config import settings
        _redis_client = _redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        from app.core.config import settings
        if settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis sliding-window rate limiter per IP.
    Limits:
      - /auth/*         : 20 req / 60s
      - /checkout/*     : 30 req / 60s
      - /api/*          : 60 req / 60s
      - everything else : 200 req / 60s

    Falls back to allowing the request if Redis is unavailable.
    """

    def _get_limit(self, path: str) -> int:
        if path.startswith("/auth/"):
            return 20
        if path.startswith("/checkout/"):
            return 30
        if path.startswith("/api/"):
            return 60
        return 200

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        limit = self._get_limit(path)
        window = 60
        bucket = path.split("/")[1] if "/" in path else path
        key = f"rl:{ip}:{bucket}"
        now = time.time()

        try:
            r = _get_redis()
            pipe = r.pipeline()
            # Remove timestamps outside window, add current, count, set expiry
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window)
            results = pipe.execute()
            count = results[2]

            if count > limit:
                logger.warning(f"[rate-limit/redis] {ip} exceeded {limit} on /{bucket}")
                return JSONResponse(
                    {"detail": "Too many requests. Please slow down."},
                    status_code=429,
                    headers={"Retry-After": str(window)},
                )
        except Exception as e:
            # Redis unavailable — fail open, log warning
            logger.warning(f"[rate-limit/redis] unavailable, skipping: {e}")

        return await call_next(request)
