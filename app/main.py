from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import uvicorn
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict
from pydantic import BaseModel, Field, validator  # Pydantic v2 uyumlu
from contextlib import asynccontextmanager

# Import custom modules
from app.config import settings
from app.firebase_manager import firebase_manager
from app.bot_manager import bot_manager, StartRequest
from app.utils.logger import get_logger
from app.utils.metrics import metrics, get_metrics_data, get_metrics_content_type

logger = get_logger("main")

# Rate limiter için fallback - Redis olmadığında in-memory kullan
try:
    from app.utils.rate_limiter import limiter, rate_limit_exceeded_handler
    RATE_LIMITING_ENABLED = True
    logger.info("Rate limiting enabled")
except Exception as e:
    logger.warning("Rate limiting disabled due to Redis unavailability", error=str(e))
    RATE_LIMITING_ENABLED = False
    # Dummy limiter oluştur
    class DummyLimiter:
        def limit(self, rate_string):
            def decorator(func):
                return func
            return decorator
        def init_app(self, app):
            pass
    
    limiter = DummyLimiter()
    
    def rate_limit_exceeded_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "detail": "Too many requests"}
        )

# ---------------- Pydantic Models ----------------

class UserRegistration(BaseModel):
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: str
    password: str

class ApiKeysRequest(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)

class BotSettingsRequest(BaseModel):
    symbol: str = Field(..., pattern=r'^[A-Z]{3,10}USDT$')
    timeframe: str = Field(..., pattern=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)$')
    leverage: int = Field(default=10, ge=1, le=125)
    order_size: float = Field(default=35.0, ge=10.0, le=10000.0)
    stop_loss: float = Field(..., ge=0.1, le=50.0)
    take_profit: float = Field(..., ge=0.1, le=100.0)

    @validator('take_profit', pre=True, always=True)
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss' in values and v <= values['stop_loss']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

# ---------------- WebSocket & Auth ----------------

connected_websockets: Dict[str, WebSocket] = {}
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        decoded_token = firebase_manager.verify_token(token)
        if not decoded_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return decoded_token
    except Exception as e:
        logger.error("Authentication failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_admin_user(current_user: dict = Depends(get_current_user)):
    if not current_user.get('admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges"
        )
    return current_user

# ---------------- Lifespan ----------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting EzyagoTrading application")
    # Setup logging
    import logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    yield
    logger.info("Shutting down EzyagoTrading application")
    await bot_manager.shutdown_all_bots()

# ---------------- FastAPI App ----------------

app = FastAPI(
    title="EzyagoTrading API",
    description="Professional Crypto Futures Trading Bot API",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production ortamına göre değiştir
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter'ı sadece aktifse ekle
if RATE_LIMITING_ENABLED:
    try:
        limiter.init_app(app)
        app.add_exception_handler(429, rate_limit_exceeded_handler)
        logger.info("Rate limiting middleware added")
    except Exception as e:
        logger.warning("Failed to add rate limiting middleware", error=str(e))

# ---------------- Logging Middleware ----------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    try:
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            "HTTP Request",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            duration=duration
        )
        metrics.record_api_request(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration=duration
        )
        return response
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(
            "HTTP Request failed",
            method=request.method,
            url=str(request.url),
            error=str(e),
            duration=duration
        )
        raise

# ---------------- Static Files ----------------

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------- Routes ----------------

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse("static/index.html")

@app.get("/login.html", response_class=HTMLResponse)
async def serve_login():
    return FileResponse("static/login.html")

@app.get("/register.html", response_class=HTMLResponse)
async def serve_register():
    return FileResponse("static/register.html")

@app.get("/dashboard.html", response_class=HTMLResponse)
async def serve_dashboard():
    return FileResponse("static/dashboard.html")

@app.get("/admin.html", response_class=HTMLResponse)
async def serve_admin():
    return FileResponse("static/admin.html")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "active_connections": len(connected_websockets),
        "active_bots": len(bot_manager.active_bots),
        "environment": settings.ENVIRONMENT,
        "rate_limiting": RATE_LIMITING_ENABLED
    }

@app.get("/metrics")
async def get_metrics():
    return JSONResponse(
        content=get_metrics_data(),
        media_type=get_metrics_content_type()
    )

@app.get("/api/firebase-config")
async def get_firebase_config():
    return {
        "apiKey": settings.FIREBASE_WEB_API_KEY,
        "authDomain": settings.FIREBASE_WEB_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_WEB_PROJECT_ID,
        "storageBucket": settings.FIREBASE_WEB_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_WEB_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_WEB_APP_ID
    }

# ---------------- User & Bot Endpoints ----------------

# Rate limiting için decorator yardımcı fonksiyonu
def apply_rate_limit(rate_string):
    if RATE_LIMITING_ENABLED:
        return limiter.limit(rate_string)
    else:
        def dummy_decorator(func):
            return func
        return dummy_decorator

@app.post("/api/user/api-keys")
async def save_api_keys(
    request: Request,
    api_keys: ApiKeysRequest, 
    current_user: dict = Depends(get_current_user)
):
    # Rate limiting manuel olarak kontrol et
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "5/minute")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        firebase_manager.update_user_api_keys(
            current_user['uid'],
            api_keys.api_key,
            api_keys.api_secret
        )
        logger.info("API keys updated", user_id=current_user['uid'])
        return {"success": True, "message": "API keys saved successfully"}
    except Exception as e:
        logger.error("Failed to save API keys", user_id=current_user['uid'], error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save API keys")

@app.get("/api/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    try:
        user_data = firebase_manager.get_user_data(current_user['uid'])
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        safe_data = {
            "email": user_data.get('email'),
            "created_at": user_data.get('created_at'),
            "subscription_status": user_data.get('subscription_status'),
            "subscription_expiry": user_data.get('subscription_expiry'),
            "has_api_keys": bool(user_data.get('binance_api_key'))
        }
        return {"success": True, "user": safe_data}
    except Exception as e:
        logger.error("Failed to get user profile", user_id=current_user['uid'], error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get user profile")

@app.post("/api/bot/start")
async def start_bot(
    request: Request,
    bot_settings: BotSettingsRequest, 
    current_user: dict = Depends(get_current_user)
):
    # Rate limiting manuel kontrol
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "3/minute")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        if not firebase_manager.is_subscription_active(current_user['uid']):
            raise HTTPException(status_code=402, detail="Active subscription required")
        start_request = StartRequest(
            symbol=bot_settings.symbol,
            timeframe=bot_settings.timeframe,
            leverage=bot_settings.leverage,
            order_size=bot_settings.order_size,
            stop_loss=bot_settings.stop_loss,
            take_profit=bot_settings.take_profit
        )
        result = await bot_manager.start_bot_for_user(current_user['uid'], start_request)
        metrics.record_bot_start(current_user['uid'], bot_settings.symbol)
        return {"success": True, "status": result}
    except Exception as e:
        logger.error("Failed to start bot", user_id=current_user['uid'], error=str(e))
        metrics.record_error("bot_start_failed", "bot_manager")
        raise HTTPException(status_code=500, detail="Failed to start bot")

@app.post("/api/bot/stop")
async def stop_bot(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    # Rate limiting manuel kontrol
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "10/minute")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        result = await bot_manager.stop_bot_for_user(current_user['uid'])
        metrics.record_bot_stop(current_user['uid'], "unknown", "manual")
        return {"success": True, "message": result.get("message", "Bot stopped")}
    except Exception as e:
        logger.error("Failed to stop bot", user_id=current_user['uid'], error=str(e))
        metrics.record_error("bot_stop_failed", "bot_manager")
        raise HTTPException(status_code=500, detail="Failed to stop bot")

@app.get("/api/bot/status")
async def get_bot_status(current_user: dict = Depends(get_current_user)):
    try:
        status_data = bot_manager.get_bot_status(current_user['uid'])
        return {"success": True, "status": status_data}
    except Exception as e:
        logger.error("Failed to get bot status", user_id=current_user['uid'], error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get bot status")

# ---------------- WebSocket ----------------

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    connected_websockets[user_id] = websocket
    logger.info("WebSocket connected", user_id=user_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
    except WebSocketDisconnect:
        connected_websockets.pop(user_id, None)
        logger.info("WebSocket disconnected", user_id=user_id)
    except Exception as e:
        connected_websockets.pop(user_id, None)
        logger.error("WebSocket error", user_id=user_id, error=str(e))

# ---------------- Error Handlers ----------------

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Endpoint not found"})

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error("Internal server error", error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# ---------------- Run ----------------

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )
