import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from app.bot_manager import bot_manager, StartRequest
from app.config import settings
from app.firebase_manager import firebase_manager, db

app = FastAPI(
    title="EzyagoTrading - Advanced Futures Bot", 
    version="5.0.0",
    description="Gelişmiş çok kullanıcılı futures trading bot sistemi"
)

bearer_scheme = HTTPBearer()

async def get_current_user(token: str = Depends(bearer_scheme)):
    """Firebase token doğrulama"""
    user_payload = firebase_manager.verify_token(token.credentials)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Geçersiz kimlik bilgisi.")
    
    uid = user_payload['uid']
    user_data = firebase_manager.get_user_data(uid)
    if not user_data:
        user_data = firebase_manager.create_user_record(uid, user_payload.get('email', ''))
    
    user_data['uid'] = uid
    user_data['role'] = 'admin' if user_payload.get('admin', False) else 'user'
    return user_data

async def get_active_subscriber(user: dict = Depends(get_current_user)):
    """Aktif abonelik kontrolü"""
    if not firebase_manager.is_subscription_active(user['uid']):
        raise HTTPException(status_code=403, detail="Aktif abonelik gerekli.")
    return user

async def get_admin_user(user: dict = Depends(get_current_user)):
    """Admin yetki kontrolü"""
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli.")
    return user

# --- Bot Management Endpoints ---

@app.post("/api/bot/start", summary="Bot başlatır")
async def start_bot_endpoint(bot_settings: StartRequest, user: dict = Depends(get_active_subscriber)):
    """Kullanıcı için trading botunu başlatır"""
    
    # Validasyon
    if bot_settings.leverage < 1 or bot_settings.leverage > 125:
        raise HTTPException(status_code=400, detail="Kaldıraç 1-125 arasında olmalı")
    
    if bot_settings.order_size < 10:
        raise HTTPException(status_code=400, detail="Minimum işlem büyüklüğü 10 USDT")
    
    if bot_settings.take_profit <= bot_settings.stop_loss:
        raise HTTPException(status_code=400, detail="Take Profit, Stop Loss'tan büyük olmalı")
    
    if not bot_settings.symbol or len(bot_settings.symbol) < 3:
        raise HTTPException(status_code=400, detail="Geçerli bir sembol seçin")
    
    result = await bot_manager.start_bot_for_user(user['uid'], bot_settings)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@app.post("/api/bot/stop", summary="Bot durdurur")
async def stop_bot_endpoint(symbol: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Kullanıcının botunu/botlarını durdurur"""
    result = await bot_manager.stop_bot_for_user(user['uid'], symbol)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@app.get("/api/bot/status", summary="Bot durumunu getirir")
async def get_bot_status_endpoint(symbol: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Kullanıcının bot durumunu döndürür"""
    return bot_manager.get_bot_status(user['uid'], symbol)

@app.get("/api/bot/symbols", summary="Mevcut sembolleri getirir")
async def get_available_symbols_endpoint(user: dict = Depends(get_current_user)):
    """Kullanıcı için mevcut futures sembollerini getirir"""
    try:
        symbols = await bot_manager.get_available_symbols(user['uid'])
        return {
            "success": True,
            "symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbols": []
        }

# --- User Management Endpoints ---

class ApiKeysRequest(BaseModel):
    api_key: str
    api_secret: str
    environment: str = "LIVE"  # LIVE veya TEST

@app.post("/api/user/save-keys", summary="API anahtarlarını kaydeder")
async def save_api_keys(request: ApiKeysRequest, user: dict = Depends(get_current_user)):
    """Kullanıcının Binance API anahtarlarını şifreli olarak kaydeder"""
    if not request.api_key.strip() or not request.api_secret.strip():
        raise HTTPException(status_code=400, detail="API Key ve Secret boş olamaz")
    
    if request.environment not in ["LIVE", "TEST"]:
        raise HTTPException(status_code=400, detail="Environment LIVE veya TEST olmalı")
    
    try:
        # API anahtarlarını kaydet
        firebase_manager.update_user_api_keys(user['uid'], request.api_key.strip(), request.api_secret.strip())
        
        # Environment ayarını da kaydet
        user_ref = firebase_manager.get_user_ref(user['uid'])
        user_ref.update({
            'environment': request.environment,
            'api_keys_updated_at': datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "success": True,
            "message": f"API anahtarları güvenli şekilde kaydedildi ({request.environment} environment)"
        }
    except Exception as e:
        print(f"API keys kaydetme hatası: {e}")
        raise HTTPException(status_code=500, detail="API anahtarları kaydedilemedi")

@app.get("/api/user/profile", summary="Kullanıcı profil bilgileri")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Kullanıcının tüm profil bilgilerini döndürür"""
    
    # Bot durumlarını al
    bot_status = bot_manager.get_bot_status(user['uid'])
    
    # Trading istatistiklerini hesapla
    try:
        trades_ref = firebase_manager.get_trades_ref(user['uid'])
        trades_data = trades_ref.get() or {}
        stats = calculate_trading_stats(trades_data)
    except Exception as e:
        print(f"Stats hesaplama hatası: {e}")
        stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "uptime_hours": 0.0
        }
    
    return {
        "email": user.get('email'),
        "subscription_status": user.get('subscription_status'),
        "subscription_expiry": user.get('subscription_expiry'),
        "registration_date": user.get('created_at'),
        "has_api_keys": bool(user.get('binance_api_key')),
        "environment": user.get('environment', 'LIVE'),
        "is_admin": user.get('role') == 'admin',
        "bot_status": bot_status,
        "stats": stats
    }

# --- Trading Statistics ---

def calculate_trading_stats(trades_data: Dict) -> Dict:
    """Trading verilerinden istatistik hesaplar"""
    if not trades_data:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "uptime_hours": 0.0
        }
    
    total_trades = len(trades_data)
    total_pnl = 0.0
    winning_trades = 0
    losing_trades = 0
    
    for trade_id, trade in trades_data.items():
        pnl = trade.get('pnl', 0.0)
        if isinstance(pnl, (int, float)):
            total_pnl += pnl
            
            if pnl > 0:
                winning_trades += 1
            elif pnl < 0:
                losing_trades += 1
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    uptime_hours = total_trades * 0.5  # Yaklaşık hesaplama
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 1),
        "uptime_hours": round(uptime_hours, 1)
    }

@app.get("/api/user/trades", summary="Kullanıcı işlem geçmişi")
async def get_user_trades(limit: int = 50, user: dict = Depends(get_current_user)):
    """Kullanıcının işlem geçmişini getirir"""
    try:
        trades_ref = firebase_manager.get_trades_ref(user['uid'])
        trades_data = trades_ref.order_by_child('timestamp').limit_to_last(limit).get() or {}
        
        # Tarihe göre sırala (en yeni önce)
        trades_list = []
        for trade_id, trade in trades_data.items():
            trade['id'] = trade_id
            trades_list.append(trade)
        
        trades_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {
            "success": True,
            "trades": trades_list,
            "count": len(trades_list)
        }
    except Exception as e:
        print(f"İşlem geçmişi alınamadı: {e}")
        return {
            "success": False,
            "trades": [],
            "error": str(e)
        }

# --- Market Data ---

@app.get("/api/market/ticker/{symbol}", summary="Sembol fiyat bilgisi")
async def get_symbol_ticker(symbol: str, user: dict = Depends(get_current_user)):
    """Belirtilen sembol için güncel fiyat bilgilerini getirir"""
    try:
        # Kullanıcının API anahtarlarını kullanarak fiyat bilgisi al
        user_data = firebase_manager.get_user_data(user['uid'])
        if not user_data:
            raise HTTPException(status_code=400, detail="Kullanıcı verisi bulunamadı")
        
        api_key = user_data.get('binance_api_key')
        api_secret = user_data.get('binance_api_secret')
        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API anahtarları ayarlanmamış")
        
        from app.binance_client import BinanceClient
        
        environment = user_data.get('environment', 'LIVE')
        testnet = environment == 'TEST'
        
        client = BinanceClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
        
        if await client.initialize():
            ticker_data = await client.get_24hr_ticker(symbol.upper())
            await client.close()
            
            if ticker_data:
                return {
                    "success": True,
                    "data": ticker_data
                }
            else:
                raise HTTPException(status_code=404, detail="Sembol bulunamadı")
        else:
            raise HTTPException(status_code=500, detail="Binance bağlantısı kurulamadı")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Ticker bilgisi alınamadı: {e}")
        raise HTTPException(status_code=500, detail=f"Fiyat bilgisi alınamadı: {str(e)}")

# --- Admin Endpoints ---

@app.get("/api/admin/system-stats", summary="Sistem istatistikleri (Admin)")
async def get_system_stats(admin: dict = Depends(get_admin_user)):
    """Admin için sistem istatistikleri"""
    try:
        # Bot manager istatistikleri
        bot_stats = bot_manager.get_system_stats()
        
        # Kullanıcı istatistikleri
        all_users = db.reference('users').get() or {}
        all_trades = db.reference('trades').get() or {}
        
        total_users = len(all_users)
        active_subscriptions = sum(1 for user in all_users.values() 
                                 if firebase_manager.is_subscription_active_by_data(user))
        
        # Toplam işlem sayısı ve PnL
        total_system_trades = 0
        total_system_pnl = 0.0
        
        for user_trades in all_trades.values():
            if isinstance(user_trades, dict):
                for trade in user_trades.values():
                    if isinstance(trade, dict):
                        total_system_trades += 1
                        pnl = trade.get('pnl', 0)
                        if isinstance(pnl, (int, float)):
                            total_system_pnl += pnl
        
        return {
            "success": True,
            "bot_stats": bot_stats,
            "user_stats": {
                "total_users": total_users,
                "active_subscriptions": active_subscriptions,
                "subscription_rate": round((active_subscriptions / total_users * 100), 1) if total_users > 0 else 0
            },
            "trading_stats": {
                "total_trades": total_system_trades,
                "total_pnl": round(total_system_pnl, 2),
                "avg_trade_pnl": round(total_system_pnl / total_system_trades, 2) if total_system_trades > 0 else 0
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        print(f"Sistem istatistikleri alınamadı: {e}")
        raise HTTPException(status_code=500, detail="Sistem istatistikleri alınamadı")

@app.get("/api/admin/users", summary="Tüm kullanıcıları listeler (Admin)")
async def get_all_users(admin: dict = Depends(get_admin_user)):
    """Admin için tüm kullanıcıları listeler"""
    try:
        all_users_data = db.reference('users').get() or {}
        
        sanitized_users = {}
        for uid, user_data in all_users_data.items():
            # Bot durumunu al
            bot_status = bot_manager.get_bot_status(uid)
            
            # Trading stats hesapla
            try:
                trades_ref = firebase_manager.get_trades_ref(uid)
                trades_data = trades_ref.get() or {}
                stats = calculate_trading_stats(trades_data)
            except:
                stats = {"total_trades": 0, "total_pnl": 0.0, "win_rate": 0.0}
            
            sanitized_users[uid] = {
                'email': user_data.get('email'),
                'subscription_status': user_data.get('subscription_status'),
                'subscription_expiry': user_data.get('subscription_expiry'),
                'created_at': user_data.get('created_at'),
                'environment': user_data.get('environment', 'LIVE'),
                'role': user_data.get('role', 'user'),
                'has_api_keys': bool(user_data.get('binance_api_key') and user_data.get('binance_api_secret')),
                'active_bots': bot_status.get('active_bots', 0),
                'total_trades': stats.get('total_trades', 0),
                'total_pnl': stats.get('total_pnl', 0.0),
                'win_rate': stats.get('win_rate', 0.0)
            }
        
        return {"success": True, "users": sanitized_users}
        
    except Exception as e:
        print(f"Admin users listesi hatası: {e}")
        raise HTTPException(status_code=500, detail="Kullanıcı listesi alınamadı")

class ActivateSubscriptionRequest(BaseModel):
    user_id: str
    days: int = 30

@app.post("/api/admin/activate-subscription", summary="Abonelik uzatır (Admin)")
async def activate_subscription(request: ActivateSubscriptionRequest, admin: dict = Depends(get_admin_user)):
    """Admin tarafından kullanıcı aboneliğini uzatır"""
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
        
        # Belirtilen gün sayısını ekle
        new_expiry = current_expiry + timedelta(days=request.days)
        
        user_ref.update({
            "subscription_status": "active",
            "subscription_expiry": new_expiry.isoformat(),
            "last_updated_by": admin['email'],
            "last_updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        print(f"Admin {admin['email']} tarafından {request.user_id} aboneliği {request.days} gün uzatıldı")
        return {
            "success": True,
            "message": f"Abonelik {request.days} gün uzatıldı",
            "new_expiry": new_expiry.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Abonelik uzatma hatası: {e}")
        raise HTTPException(status_code=500, detail="Abonelik uzatılamadı")

@app.post("/api/admin/stop-user-bots", summary="Kullanıcının tüm botlarını durdur (Admin)")
async def stop_user_bots(user_id: str, admin: dict = Depends(get_admin_user)):
    """Admin tarafından belirtilen kullanıcının tüm botlarını durdurur"""
    try:
        result = await bot_manager.stop_bot_for_user(user_id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        print(f"Admin {admin['email']} tarafından kullanıcı {user_id} botları durduruldu")
        return {
            "success": True,
            "message": f"Kullanıcı {user_id} botları durduruldu",
            "details": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Kullanıcı botları durdurma hatası: {e}")
        raise HTTPException(status_code=500, detail="Botlar durdurulamadı")

# --- Firebase Configuration ---

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

# --- Static Files & Pages ---

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
async def read_index():
    """Ana sayfa"""
    return FileResponse('static/index.html')

@app.get("/admin", include_in_schema=False)
async def read_admin_page():
    """Admin paneli"""
    return FileResponse('static/admin.html')

# --- Health Check ---

@app.get("/health", summary="Sistem sağlık kontrolü")
async def health_check():
    """Sistem durumunu kontrol eder"""
    try:
        # Firebase bağlantısını test et
        db.reference('health').set({
            'last_check': datetime.now(timezone.utc).isoformat(),
            'status': 'healthy'
        })
        
        # Bot manager istatistikleri
        bot_stats = bot_manager.get_system_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_bots": bot_stats["total_active_bots"],
            "active_users": bot_stats["total_users_with_bots"],
            "version": "5.0.0"
        }
        
    except Exception as e:
        print(f"Health check hatası: {e}")
        raise HTTPException(status_code=503, detail="Sistem sağlıksız")

# --- Error Handlers ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP hatalarını yakalar ve loglar"""
    print(f"HTTP Hata {exc.status_code}: {exc.detail} - Path: {request.url.path}")
    return {
        "error": True,
        "status_code": exc.status_code,
        "detail": exc.detail,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """500 hatalarını yakalar"""
    print(f"İç sunucu hatası: {exc} - Path: {request.url.path}")
    return {
        "error": True,
        "status_code": 500,
        "detail": "İç sunucu hatası",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# --- Startup & Shutdown Events ---

@app.on_event("startup")
async def startup_event():
    """Uygulama başlatıldığında çalışır"""
    print("🚀 EzyagoTrading Advanced Bot System başlatıldı")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Firebase Database: {settings.FIREBASE_DATABASE_URL}")
    print(f"Max bots per user: {bot_manager.max_bots_per_user}")

@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapatıldığında tüm botları güvenli şekilde durdurur"""
    print("📴 Sistem kapatılıyor, tüm botlar durduruluyor...")
    await bot_manager.shutdown_all_bots()
    print("✅ Tüm botlar güvenli şekilde durduruldu")

# --- Helper Functions ---

def is_subscription_active_by_data(user_data: dict) -> bool:
    """Kullanıcı verisinden abonelik durumunu kontrol eder"""
    if not user_data or 'subscription_expiry' not in user_data:
        return False
    try:
        expiry_date = datetime.fromisoformat(user_data['subscription_expiry'])
        return datetime.now(timezone.utc) <= expiry_date
    except ValueError:
        return False

# Firebase manager için yardımcı fonksiyon ekle
firebase_manager.is_subscription_active_by_data = is_subscription_active_by_data
