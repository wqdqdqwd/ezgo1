import os
import firebase_admin
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
import asyncio

from app.config import settings
from app.firebase_manager import firebase_manager
from app.bot_manager import bot_manager, StartRequest
from app.utils.logger import get_logger
from app.utils.metrics import metrics, get_metrics_data, get_metrics_content_type
from app.utils.rate_limiter import limiter, rate_limit_exceeded_handler
from app.utils.error_handler import safe_async_call

logger = get_logger("main")

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıç ve kapanış işlemleri"""
    logger.info("EzyagoTrading başlatılıyor...")
    
    # Ayarları doğrula
    if not settings.validate_settings():
        logger.error("Kritik ayarlar eksik - uygulama kapanıyor")
        raise Exception("Kritik ayarlar eksik")
    
    yield
    
    logger.info("Uygulama kapatılıyor...")
    await bot_manager.shutdown_all_bots()

# FastAPI uygulaması oluştur
app = FastAPI(
    title="EzyagoTrading API",
    description="Profesyonel Kripto Futures Trading Bot API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting ekle
if settings.RATE_LIMIT_ENABLED:
    limiter.init_app(app)
    app.add_exception_handler(429, rate_limit_exceeded_handler)

# Static dosyalar
app.mount("/static", StaticFiles(directory="static"), name="static")

# Authentication dependency
async def get_current_user(request: Request) -> dict:
    """Firebase ID token'ını doğrular"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Geçersiz authorization header")
            raise HTTPException(status_code=401, detail="Geçersiz authentication token")
        
        token = auth_header.split(" ")[1]
        if not token or token.strip() == "":
            logger.warning("Boş token")
            raise HTTPException(status_code=401, detail="Boş authentication token")
        
        # Token'ı doğrula (sync method)
        decoded_token = firebase_manager.verify_token(token)
        
        if not decoded_token:
            logger.warning("Token doğrulama başarısız")
            raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş token")
        
        uid = decoded_token.get('uid')
        if not uid:
            logger.error("Token'da UID bulunamadı")
            raise HTTPException(status_code=401, detail="Geçersiz token: kullanıcı ID'si eksik")
        
        logger.debug(f"Token başarıyla doğrulandı: {uid}")
        
        # Son giriş zamanını güncelle
        try:
            firebase_manager.update_user_login(uid)
        except Exception as e:
            logger.warning(f"Son giriş zamanı güncellenemedi: {e}")
        
        return decoded_token
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication hatası: {e}")
        raise HTTPException(status_code=401, detail="Authentication başarısız")

# Admin authentication
async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Admin yetkilerini kontrol eder"""
    is_admin = current_user.get('admin', False)
    if not is_admin:
        logger.warning(f"Admin olmayan kullanıcı admin erişimi denedi: {current_user.get('uid')}")
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")
    return current_user

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """İstekleri loglar ve metrics toplar"""
    start_time = datetime.now()
    
    response = await call_next(request)
    
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info(
        "İstek işlendi",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_seconds=duration,
        client_ip=request.client.host if request.client else "unknown"
    )
    
    metrics.record_api_request(
        endpoint=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration=duration
    )
    
    return response

# Ana sayfa
@app.get("/", response_class=HTMLResponse)
async def root():
    """Ana sayfa"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>EzyagoTrading</h1><p>EzyagoTrading API'ye hoş geldiniz</p>")

# Static sayfalar
@app.get("/login.html", response_class=HTMLResponse)
async def login_page():
    try:
        with open("static/login.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Login sayfası bulunamadı")

@app.get("/register.html", response_class=HTMLResponse)
async def register_page():
    try:
        with open("static/register.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Register sayfası bulunamadı")

@app.get("/dashboard.html", response_class=HTMLResponse)
async def dashboard_page():
    try:
        with open("static/dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dashboard sayfası bulunamadı")

# Sağlık kontrolü
@app.get("/health")
async def health_check():
    """Sistem sağlığını kontrol eder"""
    try:
        firebase_status = "connected" if firebase_manager.initialized else "disconnected"
        active_bots = bot_manager.get_active_bot_count()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "2.0.0",
            "firebase_status": firebase_status,
            "active_bots": active_bots,
            "environment": settings.ENVIRONMENT
        }
    except Exception as e:
        logger.error(f"Sağlık kontrolü başarısız: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }

# Metrics endpoint
@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus formatında metrics"""
    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Metrics devre dışı")
    
    try:
        metrics_data = get_metrics_data()
        return Response(
            content=metrics_data,
            media_type=get_metrics_content_type()
        )
    except Exception as e:
        logger.error(f"Metrics endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail="Metrics kullanılamıyor")

# Firebase config endpoint
@app.get("/api/firebase-config")
async def get_firebase_config():
    """Frontend için Firebase konfigürasyonu"""
    try:
        config = {
            "apiKey": settings.FIREBASE_WEB_API_KEY,
            "authDomain": settings.FIREBASE_WEB_AUTH_DOMAIN,
            "databaseURL": settings.FIREBASE_DATABASE_URL,
            "projectId": settings.FIREBASE_WEB_PROJECT_ID,
            "storageBucket": settings.FIREBASE_WEB_STORAGE_BUCKET,
            "messagingSenderId": settings.FIREBASE_WEB_MESSAGING_SENDER_ID,
            "appId": settings.FIREBASE_WEB_APP_ID
        }
        
        missing_fields = [k for k, v in config.items() if not v]
        if missing_fields:
            logger.error(f"Firebase config eksik alanlar: {missing_fields}")
            raise HTTPException(status_code=500, detail="Firebase konfigürasyonu eksik")
        
        return config
    except Exception as e:
        logger.error(f"Firebase config hatası: {e}")
        raise HTTPException(status_code=500, detail="Firebase konfigürasyon hatası")

# Authentication test endpoint
@app.get("/api/test-auth")
async def test_auth(current_user: dict = Depends(get_current_user)):
    """Authentication test"""
    try:
        return {
            "success": True,
            "message": "Authentication başarılı",
            "user": {
                "uid": current_user.get('uid'),
                "email": current_user.get('email'),
                "admin": current_user.get('admin', False)
            }
        }
    except Exception as e:
        logger.error(f"Test auth hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Kullanıcı kayıt endpoint'i
@app.post("/api/auth/register")
async def register_user(request: Request):
    """Yeni kullanıcı kaydı"""
    if settings.RATE_LIMIT_ENABLED:
        await limiter.check_request_limit(request, "5/minute")
    
    try:
        data = await request.json()
        email = data.get('email')
        uid = data.get('uid')
        
        if not email or not uid:
            raise HTTPException(status_code=400, detail="Email ve UID gerekli")
        
        user_data = firebase_manager.create_user_record(uid, email)
        
        logger.info(f"Kullanıcı kaydedildi: {email}")
        return {"success": True, "message": "Kullanıcı başarıyla kaydedildi", "user": user_data}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kullanıcı kaydı başarısız: {e}")
        raise HTTPException(status_code=500, detail="Kayıt başarısız")

# Kullanıcı profil endpoint'leri
@app.get("/api/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Kullanıcı profilini getirir"""
    try:
        user_data = firebase_manager.get_user_data(current_user['uid'])
        if not user_data:
            raise HTTPException(status_code=404, detail="Kullanıcı profili bulunamadı")
        
        profile = {
            "uid": current_user['uid'],
            "email": user_data.get('email'),
            "created_at": user_data.get('created_at'),
            "subscription_status": user_data.get('subscription_status'),
            "subscription_expiry": user_data.get('subscription_expiry'),
            "has_api_keys": bool(user_data.get('binance_api_key')),
            "role": user_data.get('role', 'user'),
            "last_login": user_data.get('last_login'),
            "subscription_active": firebase_manager.is_subscription_active(current_user['uid'])
        }
        
        return {"success": True, "profile": profile}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profil getirme başarısız: {e}")
        raise HTTPException(status_code=500, detail="Profil yüklenemedi")

@app.post("/api/user/api-keys")
async def save_api_keys(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """API anahtarlarını kaydeder"""
    if settings.RATE_LIMIT_ENABLED:
        await limiter.check_request_limit(request, "10/minute")
    
    try:
        data = await request.json()
        api_key = data.get('api_key', '').strip()
        api_secret = data.get('api_secret', '').strip()
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API key ve secret gerekli")
        
        if len(api_key) < 32 or len(api_secret) < 32:
            raise HTTPException(status_code=400, detail="Geçersiz API key formatı")
        
        success = firebase_manager.update_user_api_keys(current_user['uid'], api_key, api_secret)
        
        if not success:
            raise HTTPException(status_code=500, detail="API anahtarları kaydedilemedi")
        
        logger.info(f"API anahtarları kaydedildi: {current_user['uid']}")
        return {"success": True, "message": "API anahtarları başarıyla kaydedildi"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API anahtarları kaydetme başarısız: {e}")
        raise HTTPException(status_code=500, detail="API anahtarları kaydedilemedi")

# Bot yönetim endpoint'leri
@app.post("/api/bot/start")
async def start_bot(
    request: Request,
    bot_settings: StartRequest,
    current_user: dict = Depends(get_current_user)
):
    """Bot başlatır"""
    if settings.RATE_LIMIT_ENABLED:
        await limiter.check_request_limit(request, "5/minute")
    
    try:
        # Abonelik kontrolü
        if not firebase_manager.is_subscription_active(current_user['uid']):
            logger.warning(f"Aktif abonelik olmayan kullanıcı: {current_user['uid']}")
            raise HTTPException(status_code=403, detail="Aktif abonelik gerekli")
        
        logger.info(f"Bot başlatılıyor: {current_user['uid']}")
        
        result = await bot_manager.start_bot_for_user(current_user['uid'], bot_settings)
        
        if "error" in result:
            logger.error(f"Bot başlatma başarısız: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
        
        metrics.record_bot_start(current_user['uid'], bot_settings.symbol)
        
        logger.info(f"Bot başarıyla başlatıldı: {current_user['uid']}")
        return {"success": True, "status": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bot başlatma hatası: {e}")
        metrics.record_error("bot_start_failed", "bot_manager")
        raise HTTPException(status_code=500, detail=f"Bot başlatılamadı: {str(e)}")

@app.post("/api/bot/stop")
async def stop_bot(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Bot'u durdurur"""
    if settings.RATE_LIMIT_ENABLED:
        await limiter.check_request_limit(request, "5/minute")
    
    try:
        logger.info(f"Bot durduruluyor: {current_user['uid']}")
        
        result = await bot_manager.stop_bot_for_user(current_user['uid'])
        
        if "error" in result:
            logger.error(f"Bot durdurma başarısız: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
        
        metrics.record_bot_stop(current_user['uid'], "unknown", "manual")
        
        logger.info(f"Bot başarıyla durduruldu: {current_user['uid']}")
        return {"success": True, "message": "Bot başarıyla durduruldu"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bot durdurma hatası: {e}")
        metrics.record_error("bot_stop_failed", "bot_manager")
        raise HTTPException(status_code=500, detail=f"Bot durdurulamadı: {str(e)}")

@app.get("/api/bot/status")
async def get_bot_status(current_user: dict = Depends(get_current_user)):
    """Bot durumunu getirir"""
    try:
        logger.debug(f"Bot durumu alınıyor: {current_user['uid']}")
        
        status = bot_manager.get_bot_status(current_user['uid'])
        
        logger.debug(f"Bot durumu: {status.get('is_running', False)}")
        return {"success": True, "status": status}
        
    except Exception as e:
        logger.error(f"Bot durum getirme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Bot durumu alınamadı: {str(e)}")

@app.get("/api/user/trades")
async def get_user_trades(current_user: dict = Depends(get_current_user)):
    """Kullanıcının işlem geçmişini getirir"""
    try:
        trades = firebase_manager.get_user_trades(current_user['uid'], limit=100)
        return {"success": True, "trades": trades}
        
    except Exception as e:
        logger.error(f"İşlem geçmişi getirme hatası: {e}")
        raise HTTPException(status_code=500, detail="İşlem geçmişi alınamadı")

# Ödeme ve abonelik endpoint'leri
class PaymentNotification(BaseModel):
    transaction_hash: str
    amount: float
    currency: str = "USDT"

class SupportMessage(BaseModel):
    subject: str
    message: str
    user_email: str

@app.get("/api/payment-info")
async def get_payment_info():
    """Ödeme bilgilerini döndürür"""
    try:
        return {
            "success": True,
            "amount": settings.BOT_PRICE_USD,
            "trc20Address": settings.PAYMENT_TRC20_ADDRESS,
            "botPriceUsd": "15"
        }
    except Exception as e:
        logger.error(f"Ödeme bilgisi hatası: {e}")
        raise HTTPException(status_code=500, detail="Ödeme bilgisi alınamadı")

@app.post("/api/payment/notify")
async def notify_payment(
    request: Request,
    payment: PaymentNotification,
    current_user: dict = Depends(get_current_user)
):
    """Ödeme bildirimi alır"""
    if settings.RATE_LIMIT_ENABLED:
        await limiter.check_request_limit(request, "3/hour")
    
    try:
        payment_data = {
            "user_id": current_user['uid'],
            "user_email": current_user.get('email', ''),
            "transaction_hash": payment.transaction_hash,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "admin_notified": False
        }
        
        logger.info(f"Ödeme bildirimi alındı: {current_user['uid']}")
        
        return {
            "success": True,
            "message": "Ödeme bildirimi alındı. Admin onayı bekleniyor."
        }
        
    except Exception as e:
        logger.error(f"Ödeme bildirimi hatası: {e}")
        raise HTTPException(status_code=500, detail="Ödeme bildirimi başarısız")

@app.post("/api/support/message")
async def send_support_message(
    request: Request,
    support: SupportMessage,
    current_user: dict = Depends(get_current_user)
):
    """Destek mesajı gönderir"""
    if settings.RATE_LIMIT_ENABLED:
        await limiter.check_request_limit(request, "5/hour")
    
    try:
        support_data = {
            "user_id": current_user['uid'],
            "user_email": current_user.get('email', support.user_email),
            "subject": support.subject,
            "message": support.message,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Destek mesajı alındı: {current_user['uid']}")
        
        return {
            "success": True,
            "message": "Destek mesajınız alındı. En kısa sürede dönüş yapacağız."
        }
        
    except Exception as e:
        logger.error(f"Destek mesajı hatası: {e}")
        raise HTTPException(status_code=500, detail="Destek mesajı gönderilemedi")

# Admin endpoint'leri
@app.get("/api/admin/users")
async def get_all_users(current_user: dict = Depends(get_admin_user)):
    """Admin için tüm kullanıcıları listeler"""
    try:
        users_data = firebase_manager.get_all_users()
        
        for uid, user_data in users_data.items():
            if isinstance(user_data, dict):
                user_data['subscription_active'] = firebase_manager.is_subscription_active_by_data(user_data)
        
        logger.info(f"Admin {len(users_data)} kullanıcı listeledi")
        return {"success": True, "users": users_data}
        
    except Exception as e:
        logger.error(f"Admin kullanıcı listesi hatası: {e}")
        raise HTTPException(status_code=500, detail="Kullanıcılar getirilemedi")

@app.post("/api/admin/activate-subscription")
async def activate_user_subscription(
    request: Request,
    current_user: dict = Depends(get_admin_user)
):
    """Admin tarafından kullanıcı aboneliğini aktifleştirir"""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        days = data.get('days', 30)
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID gerekli")
        
        success = firebase_manager.extend_subscription(user_id, days)
        
        if not success:
            raise HTTPException(status_code=500, detail="Abonelik aktifleştirilemedi")
        
        logger.info(f"Admin tarafından abonelik aktifleştirildi: {user_id}")
        
        return {
            "success": True,
            "message": f"Kullanıcı aboneliği {days} gün için aktifleştirildi"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin abonelik aktifleştirme hatası: {e}")
        raise HTTPException(status_code=500, detail="Abonelik aktifleştirilemedi")

@app.get("/api/admin/bot-stats")
async def get_bot_stats(current_user: dict = Depends(get_admin_user)):
    """Admin için bot istatistikleri"""
    try:
        active_count = bot_manager.get_active_bot_count()
        active_users = bot_manager.get_all_active_users()
        
        return {
            "success": True,
            "stats": {
                "active_bot_count": active_count,
                "active_users": active_users,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Bot istatistikleri hatası: {e}")
        raise HTTPException(status_code=500, detail="Bot istatistikleri alınamadı")

# Error handler'lar
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    logger.warning(f"404 hatası: {request.url.path}")
    return JSONResponse(
        status_code=404,
        content={"error": "Bulunamadı", "detail": "İstenen kaynak bulunamadı"}
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal server error: {exc}")
    metrics.record_error("internal_server_error", "main")
    return JSONResponse(
        status_code=500,
        content={"error": "Sunucu hatası", "detail": "Beklenmeyen bir hata oluştu"}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Beklenmeyen hata: {exc}")
    metrics.record_error("unhandled_exception", "main")
    return JSONResponse(
        status_code=500,
        content={"error": "Beklenmeyen hata", "detail": "Beklenmeyen bir hata oluştu"}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
