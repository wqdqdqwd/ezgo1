import asyncio
import time
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import os

from app.bot_manager import bot_manager
from app.config import settings
from app.firebase_manager import firebase_manager, db

# Fallback logger (no complex logging)
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(
    title="EzyagoTrading - Futures Bot SaaS", 
    version="4.1.0",
    description="Gelişmiş çok kullanıcılı futures trading bot sistemi"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "DEVELOPMENT" else [
        "https://your-domain.com",
        "https://www.your-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Minimal request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)")
    return response

# Pydantic v1 models
class StartRequest(BaseModel):
    symbol: str = Field(..., min_length=6, max_length=12)
    timeframe: str = Field(..., min_length=2, max_length=3)
    leverage: int = Field(..., ge=1, le=125)
    order_size: float = Field(..., ge=10, le=10000)
    stop_loss: float = Field(..., ge=0.1, le=50.0)
    take_profit: float = Field(..., ge=0.1, le=50.0)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.endswith('USDT'):
            raise ValueError('Invalid trading symbol')
        return v.upper().strip()
    
    @validator('timeframe')
    def validate_timeframe(cls, v):
        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']
        if v not in valid_timeframes:
            raise ValueError('Invalid timeframe')
        return v
    
    @validator('take_profit')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss' in values and v <= values['stop_loss']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

class ApiKeysRequest(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 60:
            raise ValueError('Invalid Binance API key format')
        return v.strip()
    
    @validator('api_secret')
    def validate_api_secret(cls, v):
        if not v or len(v) < 60:
            raise ValueError('Invalid Binance API secret format')
        return v.strip()

class UserSettingsRequest(BaseModel):
    settings: Dict[str, Any]

class TradingStats(BaseModel):
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    uptime_hours: float = 0.0

@app.get("/api/firebase-config", summary="Frontend için Firebase yapılandırması")
async def get_firebase_config():
    """Frontend için gerekli Firebase yapılandırmasını döndürür"""
    return {
        "apiKey": settings.FIREBASE_WEB_API_KEY,
        "authDomain": settings.FIREBASE_WEB_AUTH_DOMAIN,
        "databaseURL": settings.FIREBASE_DATABASE_URL,
        "projectId": settings.FIREBASE_WEB_PROJECT_ID,
        "storageBucket": settings.FIREBASE_WEB_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_WEB_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_WEB_APP_ID,
    }

bearer_scheme = HTTPBearer()

async def get_current_user(token: str = Depends(bearer_scheme)):
    """Firebase token'ı doğrular ve kullanıcı verilerini döndürür"""
    try:
        user_payload = firebase_manager.verify_token(token.credentials)
        if not user_payload:
            raise HTTPException(status_code=401, detail="Geçersiz kimlik bilgisi.")
        
        uid = user_payload['uid']
        
        # Kullanıcı verilerini al veya oluştur
        user_data = firebase_manager.get_user_data(uid)
        if not user_data:
            user_data = firebase_manager.create_user_record(uid, user_payload.get('email', ''))
        
        user_data['uid'] = uid
        user_data['role'] = 'admin' if user_payload.get('admin', False) else 'user'
        
        return user_data
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

async def get_active_subscriber(user: dict = Depends(get_current_user)):
    """Aktif aboneliği olan kullanıcıları kontrol eder"""
    if not firebase_manager.is_subscription_active(user['uid']):
        raise HTTPException(status_code=403, detail="Aktif abonelik gerekli.")
    return user

async def get_admin_user(user: dict = Depends(get_current_user)):
    """Admin yetkisini kontrol eder"""
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli.")
    return user

# --- Bot Endpoint'leri ---
@app.post("/api/start", summary="Botu başlatır")
async def start_bot_endpoint(bot_settings: StartRequest, user: dict = Depends(get_active_subscriber)):
    """Kullanıcı için trading botunu başlatır"""
    try:
        logger.info(f"Bot start requested for user {user['uid']}, symbol {bot_settings.symbol}")
        
        # Kullanıcı ayarlarını kaydet
        await save_user_settings_internal(user['uid'], {
            'symbol': bot_settings.symbol,
            'leverage': bot_settings.leverage,
            'orderSize': bot_settings.order_size,
            'tp': bot_settings.take_profit,
            'sl': bot_settings.stop_loss,
            'timeframe': bot_settings.timeframe
        })
        
        result = await bot_manager.start_bot_for_user(user['uid'], bot_settings)
    
        if "error" in result:
            logger.error(f"Bot start failed for user {user['uid']}: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
        
        logger.info(f"Bot started successfully for user {user['uid']}")
        return {"success": True, **result}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in bot start: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/stop", summary="Botu durdurur")
async def stop_bot_endpoint(user: dict = Depends(get_current_user)):
    """Kullanıcının botunu durdurur"""
    try:
        logger.info(f"Bot stop requested for user {user['uid']}")
        
        result = await bot_manager.stop_bot_for_user(user['uid'])
        if "error" in result:
            logger.error(f"Bot stop failed for user {user['uid']}: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
        
        logger.info(f"Bot stopped successfully for user {user['uid']}")
        return {"success": True, **result}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in bot stop: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/status", summary="Bot durumunu alır")
async def get_status_endpoint(user: dict = Depends(get_current_user)):
    """Kullanıcının bot durumunu döndürür"""
    status = bot_manager.get_bot_status(user['uid'])
    
    return {
        "is_running": status.get("is_running", False),
        "status_message": status.get("status_message", "Bot durumu bilinmiyor"),
        "symbol": status.get("symbol"),
        "position_side": status.get("position_side"),
        "last_check_time": status.get("last_check_time")
    }

# --- Kullanıcı Ayarları ---
@app.post("/api/save-user-settings", summary="Kullanıcı ayarlarını kaydeder")
async def save_user_settings_endpoint(request: UserSettingsRequest, user: dict = Depends(get_current_user)):
    """Kullanıcının bot ayarlarını kaydeder"""
    await save_user_settings_internal(user['uid'], request.settings)
    return {"success": True, "message": "Ayarlar kaydedildi"}

async def save_user_settings_internal(uid: str, settings: Dict[str, Any]):
    """İç kullanım için ayar kaydetme fonksiyonu"""
    user_ref = firebase_manager.get_user_ref(uid)
    user_ref.update({
        'settings': settings,
        'settings_updated_at': datetime.now(timezone.utc).isoformat()
    })

@app.get("/api/trading-stats", summary="Trading istatistiklerini alır")
async def get_trading_stats(user: dict = Depends(get_current_user)):
    """Kullanıcının trading istatistiklerini hesaplar ve döndürür"""
    try:
        trades_ref = firebase_manager.get_trades_ref(user['uid'])
        trades_data = trades_ref.get() or {}
        
        # İstatistikleri hesapla
        stats = calculate_trading_stats(trades_data)
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Trading stats calculation error: {e}")
        return {
            "success": False,
            "stats": TradingStats().dict()
        }

def calculate_trading_stats(trades_data: Dict) -> Dict:
    """Trading verilerinden istatistik hesaplar"""
    if not trades_data:
        return TradingStats().dict()
    
    total_trades = len(trades_data)
    total_pnl = 0.0
    winning_trades = 0
    losing_trades = 0
    
    for trade_id, trade in trades_data.items():
        pnl = trade.get('pnl', 0.0)
        total_pnl += pnl
        
        if pnl > 0:
            winning_trades += 1
        elif pnl < 0:
            losing_trades += 1
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    uptime_hours = total_trades * 0.5
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 1),
        "uptime_hours": round(uptime_hours, 1)
    }

# --- Kullanıcı Profili ---
@app.get("/api/user-profile", summary="Kullanıcı profil bilgileri")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Kullanıcının tüm profil bilgilerini döndürür"""
    bot_status = bot_manager.get_bot_status(user['uid'])
    
    # Trading istatistiklerini al
    try:
        trades_ref = firebase_manager.get_trades_ref(user['uid'])
        trades_data = trades_ref.get() or {}
        stats = calculate_trading_stats(trades_data)
    except Exception as e:
        logger.error(f"Stats calculation error: {e}")
        stats = TradingStats().dict()
    
    # Kullanıcı ayarlarını al
    user_settings = user.get('settings', {
        'leverage': 10,
        'orderSize': 20,
        'tp': 4,
        'sl': 2,
        'symbol': 'BTCUSDT',
        'timeframe': '15m'
    })
    
    return {
        "email": user.get('email'),
        "subscription_status": user.get('subscription_status'),
        "subscription_expiry": user.get('subscription_expiry'),
        "registration_date": user.get('created_at'),
        "has_api_keys": bool(user.get('binance_api_key')),
        "payment_address": settings.PAYMENT_TRC20_ADDRESS,
        "is_admin": user.get('role') == 'admin',
        "server_ips": ["18.156.158.53", "18.156.42.200", "52.59.103.54"],
        "bot_last_check": bot_status.get("last_check_time"),
        "settings": user_settings,
        "stats": stats
    }

# --- API Anahtarları ---
@app.post("/api/save-keys", summary="API anahtarlarını kaydeder")
async def save_api_keys(api_keys: ApiKeysRequest, user: dict = Depends(get_current_user)):
    """Kullanıcının Binance API anahtarlarını şifreli olarak kaydeder"""
    try:
        logger.info(f"API keys save requested for user {user['uid']}")
        
        firebase_manager.update_user_api_keys(user['uid'], api_keys.api_key, api_keys.api_secret)
        
        logger.info(f"API keys saved successfully for user {user['uid']}")
        return {"success": True, "message": "API anahtarları güvenli şekilde kaydedildi"}
    except Exception as e:
        logger.error(f"Failed to save API keys for user {user['uid']}: {e}")
        raise HTTPException(status_code=500, detail="API anahtarları kaydedilemedi")

# --- Health Check ---
@app.get("/health", summary="Sistem sağlık kontrolü")
async def health_check():
    """Gelişmiş sistem durumu kontrolü"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "4.1.0",
            "components": {}
        }
        
        # Firebase health check
        try:
            db.reference('health').set({
                'last_check': datetime.now(timezone.utc).isoformat(),
                'status': 'healthy'
            })
            health_status["components"]["firebase"] = "healthy"
        except Exception as e:
            health_status["components"]["firebase"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # Bot manager health check
        try:
            active_bots = len(bot_manager.active_bots)
            health_status["components"]["bot_manager"] = "healthy"
            health_status["active_bots"] = active_bots
        except Exception as e:
            health_status["components"]["bot_manager"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # Overall status
        if health_status["status"] == "degraded":
            return JSONResponse(
                status_code=503,
                content=health_status
            )
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
        )

# --- Admin Endpoint'leri ---
@app.get("/api/admin/users", summary="Tüm kullanıcıları listeler (Admin)")
async def get_all_users(admin: dict = Depends(get_admin_user)):
    """Admin için tüm kullanıcıları listeler"""
    try:
        all_users_data = db.reference('users').get() or {}
        
        sanitized_users = {}
        for uid, user_data in all_users_data.items():
            # Her kullanıcı için trading stats hesapla
            try:
                trades_ref = firebase_manager.get_trades_ref(uid)
                trades_data = trades_ref.get() or {}
                stats = calculate_trading_stats(trades_data)
            except:
                stats = TradingStats().dict()
            
            sanitized_users[uid] = {
                'email': user_data.get('email'),
                'subscription_status': user_data.get('subscription_status'),
                'subscription_expiry': user_data.get('subscription_expiry'),
                'created_at': user_data.get('created_at'),
                'role': user_data.get('role', 'user'),
                'has_api_keys': bool(user_data.get('binance_api_key') and user_data.get('binance_api_secret')),
                'total_trades': stats.get('total_trades', 0),
                'total_pnl': stats.get('total_pnl', 0.0)
            }
        
        return {"users": sanitized_users}
    except Exception as e:
        logger.error(f"Admin users list error: {e}")
        raise HTTPException(status_code=500, detail="Kullanıcı listesi alınamadı")

class ActivateSubscriptionRequest(BaseModel):
    user_id: str

@app.post("/api/admin/activate-subscription", summary="Abonelik uzatır (Admin)")
async def activate_subscription(request: ActivateSubscriptionRequest, admin: dict = Depends(get_admin_user)):
    """Admin tarafından kullanıcı aboneliğini 30 gün uzatır"""
    try:
        user_ref = firebase_manager.get_user_ref(request.user_id)
        user_data = user_ref.get()
        
        if not user_data:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
        
        # Mevcut abonelik bitiş tarihini al
        current_expiry_str = user_data.get('subscription_expiry')
        current_expiry = datetime.now(timezone.utc)
        
        if current_expiry_str:
            try:
                expiry_from_db = datetime.fromisoformat(current_expiry_str.replace('Z', '+00:00'))
                if expiry_from_db > current_expiry:
                    current_expiry = expiry_from_db
            except ValueError:
                logger.error(f"Invalid date format: {current_expiry_str}")
        
        # 30 gün ekle
        new_expiry = current_expiry + timedelta(days=30)
        
        user_ref.update({
            "subscription_status": "active",
            "subscription_expiry": new_expiry.isoformat(),
            "last_updated_by": admin['email'],
            "last_updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Admin {admin['email']} extended subscription for {request.user_id}")
        return {"success": True, "message": f"Abonelik 30 gün uzatıldı", "new_expiry": new_expiry.isoformat()}
        
    except Exception as e:
        logger.error(f"Subscription extension error: {e}")
        raise HTTPException(status_code=500, detail="Abonelik uzatılamadı")

# --- Static Files ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
async def read_index():
    """Ana sayfa"""
    return FileResponse('static/index.html')

@app.get("/admin", include_in_schema=False)
async def read_admin_page(admin: dict = Depends(get_admin_user)):
    """Admin paneli - yetki kontrolü ile"""
    return FileResponse('static/admin.html')

# --- Sistem Events ---
@app.on_event("startup")
async def startup_event():
    """Uygulama başlatıldığında çalışır"""
    port = os.getenv("PORT", "8000")
    logger.info(f"🚀 EzyagoTrading Backend started on port {port}")

@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapatıldığında tüm botları güvenli şekilde durdurur"""
    logger.info("📴 System shutting down, stopping all bots...")
    await bot_manager.shutdown_all_bots()
    logger.info("✅ All bots stopped safely")

# --- Error Handlers ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP hatalarını yakalar ve loglar"""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail} - {request.url.path}")
    
    return {
        "error": True,
        "status_code": exc.status_code,
        "detail": exc.detail,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """500 hatalarını yakalar"""
    logger.error(f"Internal Server Error: {exc} - {request.url.path}")
    
    return {
        "error": True,
        "status_code": 500,
        "detail": "İç sunucu hatası",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
