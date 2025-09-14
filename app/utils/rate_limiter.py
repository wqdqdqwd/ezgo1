import time
from typing import Dict, List
from fastapi import Request, HTTPException
from app.utils.logger import get_logger

logger = get_logger("rate_limiter")

class RateLimiter:
    """Basit rate limiter"""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
        
    def init_app(self, app):
        """FastAPI app'e rate limiter ekle"""
        self.app = app
        
    async def check_request_limit(self, request: Request, limit_str: str):
        """Rate limit kontrolü yapar"""
        try:
            # Limit string'ini parse et (örn: "5/minute")
            count, period = limit_str.split('/')
            count = int(count)
            
            if period == 'minute':
                window = 60
            elif period == 'hour':
                window = 3600
            elif period == 'day':
                window = 86400
            else:
                window = 60  # Default
                
            # Client IP'sini al
            client_ip = request.client.host if request.client else "unknown"
            current_time = time.time()
            
            # Bu client için geçmiş istekleri al
            if client_ip not in self.requests:
                self.requests[client_ip] = []
                
            # Eski istekleri temizle
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip] 
                if current_time - req_time < window
            ]
            
            # Limit kontrolü
            if len(self.requests[client_ip]) >= count:
                logger.warning(f"Rate limit exceeded", client_ip=client_ip, limit=limit_str)
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
                
            # İsteği kaydet
            self.requests[client_ip].append(current_time)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit check error", error=str(e))
            # Hata durumunda geçir
            pass

# Global limiter
limiter = RateLimiter()

async def rate_limit_exceeded_handler(request: Request, exc: HTTPException):
    """Rate limit aşıldığında çağrılır"""
    return {"error": "Rate limit exceeded", "detail": "Too many requests"}
