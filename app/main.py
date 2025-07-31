import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
from functools import wraps 

from app.bot_manager import bot_manager, StartRequest # StartRequest'i de import edin
from app.config import settings
from app.firebase_manager import firebase_manager, db

app = FastAPI(
    title="Binance Futures Bot SaaS", 
    version="3.2.0",
    description="Kullanıcı tarafından yapılandırılabilen, çok kullanıcılı ticaret botu."
)

# StartRequest modeli zaten yukarıda tanımlı olduğu için burada tekrar tanımlamaya gerek yok.
# class StartRequest(BaseModel):
#    symbol: str
#    timeframe: str = "15m" 
#    leverage: int = Field(..., gt=0, le=125) 
#    order_size: float = Field(..., ge=10.0) 
#    stop_loss: float = Field(..., gt=0)
#    take_profit: float = Field(..., gt=0)

@app.get("/api/firebase-config", summary="Frontend için Firebase yapılandırmasını döndürür")
async def get_firebase_config():
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
    # firebase_manager.verify_token zaten token'ı doğrular ve decoded payload'u döndürür.
    user_payload = firebase_manager.verify_token(token.credentials)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Geçersiz kimlik bilgisi.")
    
    uid = user_payload['uid']
    
    # Realtime Database'den kullanıcı verilerini çek
    user_data = firebase_manager.get_user_data(uid)
    
    # Eğer kullanıcı Realtime Database'de yoksa (yeni kayıt), oluştur.
    if not user_data:
        user_data = firebase_manager.create_user_record(uid, user_payload.get('email', ''))
    
    user_data['uid'] = uid # UID'yi user_data'ya ekle
    
    # KRİTİK DEĞİŞİKLİK: 'admin' rolünü doğrudan Firebase ID Token'ın custom claims'inden al.
    user_data['role'] = 'admin' if user_payload.get('admin', False) else 'user'
    
    return user_data

async def get_active_subscriber(user: dict = Depends(get_current_user)):
    if not firebase_manager.is_subscription_active(user['uid']):
        raise HTTPException(status_code=403, detail="Bu işlemi yapmak için aktif bir aboneliğiniz bulunmuyor.")
    return user

async def get_admin_user(user: dict = Depends(get_current_user)):
    # Bu fonksiyon şimdi get_current_user tarafından döndürülen ve
    # custom claim'den alınmış 'role' bilgisini kullanacak.
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Bu işlem için yönetici yetkiniz yok.")
    return user

# --- Bot Başlatma Endpoint'i (Güncellendi) ---
@app.post("/api/start", summary="Kullanıcı için botu başlatır")
async def start_bot_endpoint(bot_settings: StartRequest, user: dict = Depends(get_active_subscriber)):
    """
    Kullanıcıdan gelen tüm ayarları alır ve bot yöneticisine gönderir.
    """
    # bot_settings objesini doğrudan bot_manager'a ilettik.
    result = await bot_manager.start_bot_for_user(user['uid'], bot_settings)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/stop", summary="Kullanıcı için botu durdurur")
async def stop_bot_endpoint(user: dict = Depends(get_current_user)):
    result = await bot_manager.stop_bot_for_user(user['uid'])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/api/status", summary="Kullanıcının bot durumunu alır")
async def get_status_endpoint(user: dict = Depends(get_current_user)):
    return bot_manager.get_bot_status(user['uid'])

# --- Kullanıcı Profil Endpoint'i (Güncellendi) ---
@app.get("/api/user-profile", summary="Kullanıcı profil bilgilerini alır")
async def get_user_profile(user: dict = Depends(get_current_user)):
    # bot_core.py'den gelen 'last_check_time' bilgisini de burada döndürebiliriz.
    bot_status = bot_manager.get_bot_status(user['uid'])
    
    return {
        "email": user.get('email'),
        "subscription_status": user.get('subscription_status'),
        "subscription_expiry": user.get('subscription_expiry'),
        "has_api_keys": bool(user.get('binance_api_key')),
        "payment_address": settings.PAYMENT_TRC20_ADDRESS,
        "is_admin": user.get('role') == 'admin', 
        "server_ips": ["18.156.158.53", "18.156.42.200", "52.59.103.54"], # Güncellediğiniz IP'ler
        "bot_last_subscription_check": bot_status.get("last_check_time") # Yeni eklendi
    }

class ApiKeysRequest(BaseModel):
    api_key: str
    api_secret: str

@app.post("/api/save-keys", summary="Kullanıcının API anahtarlarını kaydeder")
async def save_api_keys(request: ApiKeysRequest, user: dict = Depends(get_current_user)):
    firebase_manager.update_user_api_keys(user['uid'], request.api_key, request.api_secret)
    return {"success": True, "message": "API anahtarları başarıyla kaydedildi."} 

@app.get("/api/admin/users", summary="Tüm kullanıcıları listeler (Admin Gerekli)")
async def get_all_users(admin: dict = Depends(get_admin_user)):
    all_users_data = db.reference('users').get() 
    
    sanitized_users = {}
    if all_users_data:
        for uid, user_data in all_users_data.items():
            sanitized_users[uid] = {
                'email': user_data.get('email'),
                'subscription_status': user_data.get('subscription_status'),
                'subscription_expiry': user_data.get('subscription_expiry'),
                'created_at': user_data.get('created_at'), 
                'role': user_data.get('role', 'user'), 
                'has_api_keys': bool(user_data.get('binance_api_key') and user_data.get('binance_api_secret'))
            }
    return {"users": sanitized_users} 

class ActivateSubscriptionRequest(BaseModel):
    user_id: str

@app.post("/api/admin/activate-subscription", summary="Kullanıcı aboneliğini 30 gün uzatır (Admin Gerekli)")
async def activate_subscription(request: ActivateSubscriptionRequest, admin: dict = Depends(get_admin_user)):
    user_ref = firebase_manager.get_user_ref(request.user_id)
    user_data = user_ref.get()
    
    if not user_data:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    
    current_expiry_str = user_data.get('subscription_expiry')
    current_expiry = datetime.now(timezone.utc)
    if current_expiry_str:
        try:
            expiry_from_db = datetime.fromisoformat(current_expiry_str)
            if expiry_from_db > current_expiry:
                current_expiry = expiry_from_db
        except ValueError:
            print(f"Uyarı: Geçersiz subscription_expiry formatı: {current_expiry_str}. Şimdiki zaman kullanılıyor.")
            current_expiry = datetime.now(timezone.utc)
    
    new_expiry = current_expiry + timedelta(days=30)
    
    user_ref.update({
        "subscription_status": "active",
        "subscription_expiry": new_expiry.isoformat()
    })
    return {"success": True, "message": f"{request.user_id} için abonelik 30 gün uzatıldı."}

# Static dosyaları ve ana HTML dosyalarını sunma
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
async def read_index():
    return FileResponse('static/index.html')

@app.get("/admin", include_in_schema=False)
async def read_admin_index(admin: dict = Depends(get_admin_user)):
    # Bu endpoint'e ulaşılırsa admin yetkisi zaten doğrulanmıştır.
    return FileResponse('static/admin.html')

@app.on_event("shutdown")
async def shutdown_event():
    await bot_manager.shutdown_all_bots()