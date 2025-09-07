import asyncio
import time
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
from functools import wraps 
from typing import Optional, Dict, Any
import os

from app.bot_manager import bot_manager, StartRequest
from app.config import settings
from app.firebase_manager import firebase_manager, db
from app.utils.logger import setup_logging, get_logger
from app.utils.rate_limiter import limiter, rate_limit_exceeded_handler
from app.utils.metrics import metrics, get_metrics_data, get_metrics_content_type
from app.utils.validation import EnhancedStartRequest, EnhancedApiKeysRequest, validate_user_input
from slowapi.errors import RateLimitExceeded

# Setup logging
setup_logging()
logger = get_logger("main")
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

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Middleware for request logging and metrics
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown"
    )
    
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Record metrics
    metrics.record_api_request(
        endpoint=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration=duration
    )
    
    # Log response
    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=f"{duration:.3f}s"
    )
    
    return response

# YENİ: Kullanıcı ayarları modeli
class UserSettingsRequest(BaseModel):
    settings: Dict[str, Any]

# YENİ: Trading istatistikleri modeli  
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
        logger.error("Authentication failed", error=str(e))
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
@limiter.limit("3/minute")  # Dakikada 3 bot başlatma
async def start_bot_endpoint(request: Request, bot_settings: EnhancedStartRequest, user: dict = Depends(get_active_subscriber)):
    """Kullanıcı için trading botunu başlatır"""
    try:
        logger.info("Bot start requested", user_id=user['uid'], symbol=bot_settings.symbol)
    
        # Kullanıcı ayarlarını kaydet
        await save_user_settings_internal(user['uid'], {
            'symbol': bot_settings.symbol,
            'leverage': bot_settings.leverage,
            'orderSize': bot_settings.order_size,
            'tp': bot_settings.take_profit,
            'sl': bot_settings.stop_loss,
            'timeframe': bot_settings.timeframe
        })
    
        # Convert to original StartRequest for compatibility
        start_request = StartRequest(
            symbol=bot_settings.symbol,
            timeframe=bot_settings.timeframe,
            leverage=bot_settings.leverage,
            order_size=bot_settings.order_size,
            stop_loss=bot_settings.stop_loss,
            take_profit=bot_settings.take_profit
        )
        
        result = await bot_manager.start_bot_for_user(user['uid'], start_request)
    
        if "error" in result:
            logger.error("Bot start failed", user_id=user['uid'], error=result["error"])
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Record metrics
        metrics.record_bot_start(user['uid'], bot_settings.symbol)
        
        logger.info("Bot started successfully", user_id=user['uid'], symbol=bot_settings.symbol)
        return {"success": True, **result}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in bot start", user_id=user['uid'], error=str(e))
        metrics.record_error("bot_start_error", "main")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/stop", summary="Botu durdurur")
@limiter.limit("10/minute")
async def stop_bot_endpoint(request: Request, user: dict = Depends(get_current_user)):
    """Kullanıcının botunu durdurur"""
    try:
        logger.info("Bot stop requested", user_id=user['uid'])
        
        result = await bot_manager.stop_bot_for_user(user['uid'])
        if "error" in result:
            logger.error("Bot stop failed", user_id=user['uid'], error=result["error"])
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Record metrics
        metrics.record_bot_stop(user['uid'], "unknown", "manual")
        
        logger.info("Bot stopped successfully", user_id=user['uid'])
        return {"success": True, **result}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in bot stop", user_id=user['uid'], error=str(e))
        metrics.record_error("bot_stop_error", "main")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/status", summary="Bot durumunu alır")
@limiter.limit("30/minute")
async def get_status_endpoint(request: Request, user: dict = Depends(get_current_user)):
    """Kullanıcının bot durumunu döndürür"""
    status = bot_manager.get_bot_status(user['uid'])
    
    # Update active bots metric
    active_bot_count = len([bot for bot in bot_manager.active_bots.values() if bot.status.get("is_running", False)])
    metrics.update_active_bots(active_bot_count)
    
    return {
        "is_running": status.get("is_running", False),
        "status_message": status.get("status_message", "Bot durumu bilinmiyor"),
        "symbol": status.get("symbol"),
        "position_side": status.get("position_side"),
        "last_check_time": status.get("last_check_time")
    }

# --- YENİ: Kullanıcı Ayarları Endpoint'leri ---
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
        print(f"Trading stats hesaplama hatası: {e}")
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
    
    # Uptime hesaplama (basit yaklaşım)
    uptime_hours = total_trades * 0.5  # Her trade yaklaşık 30 dakika varsayımı
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 1),
        "uptime_hours": round(uptime_hours, 1)
    }

# --- Kullanıcı Profili (GÜNCELLENDİ) ---
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
        print(f"Stats hesaplama hatası: {e}")
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
@limiter.limit("5/minute")
async def save_api_keys(request: Request, api_keys: EnhancedApiKeysRequest, user: dict = Depends(get_current_user)):
    """Kullanıcının Binance API anahtarlarını şifreli olarak kaydeder"""
    try:
        logger.info("API keys save requested", user_id=user['uid'])
        
        firebase_manager.update_user_api_keys(user['uid'], api_keys.api_key, api_keys.api_secret)
        
        logger.info("API keys saved successfully", user_id=user['uid'])
        return {"success": True, "message": "API anahtarları güvenli şekilde kaydedildi"}
    except Exception as e:
        logger.error("Failed to save API keys", user_id=user['uid'], error=str(e))
        metrics.record_error("api_keys_save_error", "main")
        raise HTTPException(status_code=500, detail="API anahtarları kaydedilemedi")

# --- Metrics Endpoint ---
@app.get("/metrics", summary="Prometheus metrics")
async def get_metrics():
    """Prometheus formatında metrics döndürür"""
    return Response(
        content=get_metrics_data(),
        media_type=get_metrics_content_type()
    )

# --- Health Check (Enhanced) ---
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
            metrics.update_active_bots(active_bots)
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
        logger.error("Health check failed", error=str(e))
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
        print(f"Admin users listesi hatası: {e}")
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
                print(f"Geçersiz tarih formatı: {current_expiry_str}")
        
        # 30 gün ekle
        new_expiry = current_expiry + timedelta(days=30)
        
        user_ref.update({
            "subscription_status": "active",
            "subscription_expiry": new_expiry.isoformat(),
            "last_updated_by": admin['email'],
            "last_updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        print(f"Admin {admin['email']} tarafından {request.user_id} aboneliği uzatıldı")
        return {"success": True, "message": f"Abonelik 30 gün uzatıldı", "new_expiry": new_expiry.isoformat()}
        
    except Exception as e:
        print(f"Abonelik uzatma hatası: {e}")
        raise HTTPException(status_code=500, detail="Abonelik uzatılamadı")

# YENİ: Bot performance endpoint'i
@app.get("/api/admin/bot-performance", summary="Genel bot performansı (Admin)")
async def get_bot_performance(admin: dict = Depends(get_admin_user)):
    """Tüm sistemin genel performans istatistikleri"""
    try:
        all_users = db.reference('users').get() or {}
        all_trades = db.reference('trades').get() or {}
        
        total_users = len(all_users)
        active_subscriptions = sum(1 for user in all_users.values() 
                                 if firebase_manager.is_subscription_active_by_data(user))
        
        # Genel trading stats
        total_system_trades = 0
        total_system_pnl = 0.0
        
        for user_trades in all_trades.values():
            if isinstance(user_trades, dict):
                for trade in user_trades.values():
                    if isinstance(trade, dict):
                        total_system_trades += 1
                        total_system_pnl += trade.get('pnl', 0.0)
        
        # Aktif bot sayısı
        active_bots = len([bot for bot in bot_manager.active_bots.values() 
                          if bot.status.get("is_running", False)])
        
        return {
            "total_users": total_users,
            "active_subscriptions": active_subscriptions,
            "active_bots": active_bots,
            "total_trades": total_system_trades,
            "total_pnl": round(total_system_pnl, 2),
            "success_rate": 0.0  # Bu hesaplanabilir
        }
    except Exception as e:
        print(f"Performance stats hatası: {e}")
        raise HTTPException(status_code=500, detail="Performance verileri alınamadı")

# --- YENİ: Kullanıcı Ayarları Endpoint'leri ---
@app.post("/api/save-user-settings", summary="Kullanıcı ayarlarını kaydeder")  
async def save_user_settings_endpoint(request: UserSettingsRequest, user: dict = Depends(get_current_user)):
    """Kullanıcının kişisel bot ayarlarını kaydeder"""
    try:
        await save_user_settings_internal(user['uid'], request.settings)
        return {"success": True, "message": "Ayarlar kaydedildi"}
    except Exception as e:
        print(f"Ayar kaydetme hatası: {e}")
        raise HTTPException(status_code=500, detail="Ayarlar kaydedilemedi")

# --- YENİ: Market Data Endpoint'leri ---
@app.get("/api/market-data/{symbol}", summary="Market verilerini alır")
async def get_market_data(symbol: str, user: dict = Depends(get_current_user)):
    """Belirtilen sembol için market verilerini döndürür"""
    try:
        # Bu endpoint gelecekte WebSocket ile real-time data sağlayabilir
        # Şimdilik basit bir response döndürüyoruz
        return {
            "symbol": symbol.upper(),
            "price": 0.0,  # Real-time price buraya eklenecek
            "change_24h": 0.0,
            "volume_24h": 0.0,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        print(f"Market data hatası: {e}")
        raise HTTPException(status_code=500, detail="Market verisi alınamadı")

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
    logger.info("🚀 EzyagoTrading Backend started", 
                environment=settings.ENVIRONMENT,
                port=port,
                firebase_db=settings.FIREBASE_DATABASE_URL)

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
    logger.error("HTTP Exception", 
                status_code=exc.status_code, 
                detail=exc.detail, 
                path=request.url.path)
    
    metrics.record_error(f"http_{exc.status_code}", "main")
    
    return {
        "error": True,
        "status_code": exc.status_code,
        "detail": exc.detail,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """500 hatalarını yakalar"""
    logger.error("Internal Server Error", error=str(exc), path=request.url.path)
    metrics.record_error("internal_server_error", "main")
    
    return {
        "error": True,
        "status_code": 500,
        "detail": "İç sunucu hatası",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
