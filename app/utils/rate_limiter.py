from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import redis
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("rate_limiter")

# Redis connection for distributed rate limiting
try:
    redis_client = redis.Redis(
        host=getattr(settings, 'REDIS_HOST', 'localhost'),
        port=getattr(settings, 'REDIS_PORT', 6379),
        db=getattr(settings, 'REDIS_DB', 0),
        decode_responses=True
    )
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established for rate limiting")
except Exception as e:
    logger.warning("Redis not available, using in-memory rate limiting", error=str(e))
    redis_client = None

def get_user_id_from_request(request: Request):
    """
    Request'ten user ID'yi çıkarır (rate limiting için)
    """
    try:
        # Authorization header'dan user ID'yi al
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # Bu gerçek implementasyonda token'dan user ID çıkarılmalı
            # Şimdilik IP address kullanıyoruz
            return get_remote_address(request)
        return get_remote_address(request)
    except Exception:
        return get_remote_address(request)

# Rate limiter instance
limiter = Limiter(
    key_func=get_user_id_from_request,
    storage_uri=f"redis://localhost:6379" if redis_client else "memory://",
    default_limits=["1000/hour"]
)

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Rate limit aşıldığında custom response
    """
    logger.warning(
        "Rate limit exceeded",
        client_ip=get_remote_address(request),
        path=request.url.path,
        limit=str(exc.detail)
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": "Too many requests. Please try again later.",
            "retry_after": exc.retry_after if hasattr(exc, 'retry_after') else 60
        }
    )