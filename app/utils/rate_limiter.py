from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import redis
from app.config import settings
from app.utils.logger import get_logger
import time
from typing import Dict

logger = get_logger("rate_limiter")

# In-memory rate limiting for fallback
class InMemoryLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        current_time = time.time()
        if key not in self.requests:
            self.requests[key] = []
        
        # Eski requestleri temizle
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if current_time - req_time < window
        ]
        
        # Limit kontrolü
        if len(self.requests[key]) >= limit:
            return False
        
        # Yeni request ekle
        self.requests[key].append(current_time)
        return True

in_memory_limiter = InMemoryLimiter()

# Redis connection for distributed rate limiting
try:
    redis_client = redis.Redis(
        host=getattr(settings, 'REDIS_HOST', 'localhost'),
        port=getattr(settings, 'REDIS_PORT', 6379),
        db=getattr(settings, 'REDIS_DB', 0),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established for rate limiting")
    REDIS_AVAILABLE = True
except Exception as e:
    logger.warning("Redis not available, using in-memory rate limiting", error=str(e))
    redis_client = None
    REDIS_AVAILABLE = False

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
if REDIS_AVAILABLE:
    limiter = Limiter(
        key_func=get_user_id_from_request,
        storage_uri=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
        default_limits=["1000/hour"]
    )
else:
    limiter = Limiter(
        key_func=get_user_id_from_request,
        storage_uri="memory://",
        default_limits=["1000/hour"]
    )

# Rate limit check function
async def check_rate_limit(request: Request, rate_string: str) -> bool:
    """
    Rate limit kontrolü yapar
    rate_string format: "5/minute", "10/hour", etc.
    """
    try:
        # Parse rate string
        rate_parts = rate_string.split('/')
        if len(rate_parts) != 2:
            return True  # Invalid format, allow
        
        limit = int(rate_parts[0])
        period = rate_parts[1]
        
        # Convert period to seconds
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }.get(period, 60)
        
        # Get user identifier
        user_key = get_user_id_from_request(request)
        
        # Check with in-memory limiter as fallback
        if not REDIS_AVAILABLE:
            return in_memory_limiter.is_allowed(user_key, limit, period_seconds)
        
        # Use Redis if available
        current_time = int(time.time())
        window_start = current_time - period_seconds
        
        # Redis sliding window algorithm
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(user_key, 0, window_start)
        pipe.zcard(user_key)
        pipe.zadd(user_key, {str(current_time): current_time})
        pipe.expire(user_key, period_seconds)
        
        results = pipe.execute()
        request_count = results[1]
        
        return request_count < limit
        
    except Exception as e:
        logger.error("Rate limit check failed", error=str(e))
        return True  # Allow on error

# Enhanced limiter class
class EnhancedLimiter:
    def __init__(self, base_limiter):
        self.base_limiter = base_limiter
    
    def limit(self, rate_string):
        """Decorator for rate limiting"""
        def decorator(func):
            if REDIS_AVAILABLE:
                return self.base_limiter.limit(rate_string)(func)
            else:
                # For in-memory, return function as-is and check manually
                return func
        return decorator
    
    def init_app(self, app):
        """Initialize with FastAPI app"""
        if REDIS_AVAILABLE:
            self.base_limiter.init_app(app)
    
    async def check_request_limit(self, request: Request, rate_string: str):
        """Manual rate limit check"""
        if not await check_rate_limit(request, rate_string):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

# Create enhanced limiter
limiter = EnhancedLimiter(limiter)

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Rate limit aşıldığında custom response
    """
    logger.warning(
        "Rate limit exceeded",
        client_ip=get_remote_address(request),
        path=request.url.path,
        limit=str(exc.detail) if hasattr(exc, 'detail') else 'unknown'
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": "Too many requests. Please try again later.",
            "retry_after": getattr(exc, 'retry_after', 60)
        }
    )
