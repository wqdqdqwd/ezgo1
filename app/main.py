import json
import os
import uvicorn
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from starlette.background import BackgroundTasks
from app.config import Settings
from app.firebase_manager import FirebaseManager
from app.encryption_service import EncryptionService
from app.bot_manager import BotManager

# Ortam değişkenlerini yükle
settings = Settings()

# Firebase ve şifreleme hizmetlerini başlat
firebase_manager = FirebaseManager(settings)
encryption_service = EncryptionService(settings.ENCRYPTION_KEY)

# Bot yöneticisini başlat
bot_manager = BotManager()

# FastAPI uygulamasını başlat
app = FastAPI(title="Binance Bot Backend", version="1.0.0")

# WebSocket bağlantıları için bir sözlük
ws_connections: Dict[str, Any] = {}

# Pydantic modelleri
class ApiKeysRequest(BaseModel):
    uid: str
    api_key: str
    api_secret: str

class BotRequest(BaseModel):
    uid: str

class StartRequest(BaseModel):
    uid: str
    settings: dict # Artık ayarlar dict olarak gönderilecek

# Uygulama başlatıldığında ve kapatıldığında çalışacak olaylar
@app.on_event("startup")
async def startup_event():
    print("Uygulama başlatılıyor...")
    await firebase_manager.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    print("Uygulama kapatılıyor...")
    await bot_manager.shutdown_all_bots()
    print("Uygulama başarıyla kapatıldı.")

# Statik dosyaları (HTML, CSS, JS) sunar
@app.get("/")
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# Botu başlatma endpoint'i
@app.post("/start-bot")
async def start_bot(request: Request):
    try:
        data = await request.json()
        uid = data.get("uid")
        bot_settings = data.get("settings")
        
        if not uid or not bot_settings:
            raise ValueError("Eksik UID veya bot ayarları.")
        
        # BotManager'a StartRequest modelini aktar
        result = await bot_manager.start_bot_for_user(uid, bot_settings)
        
        if "error" in result:
            return JSONResponse(status_code=400, content={"success": False, "error": result["error"]})
        
        return JSONResponse(content={"success": True, "message": "Bot başarıyla başlatıldı."})
        
    except Exception as e:
        print(f"Hata: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# Botu durdurma endpoint'i
@app.post("/stop-bot")
async def stop_bot(request: BotRequest):
    result = await bot_manager.stop_bot_for_user(request.uid)
    if "error" in result:
        return JSONResponse(status_code=400, content={"success": False, "error": result["error"]})
    return JSONResponse(content={"success": True, "message": "Bot durduruldu."})

# Bot durumunu alma endpoint'i
@app.get("/bot-status")
async def get_bot_status(uid: str):
    status = bot_manager.get_bot_status(uid)
    return JSONResponse(content=status)

# API anahtarlarını kaydetme endpoint'i
@app.post("/save-api-keys")
async def save_api_keys(request: ApiKeysRequest):
    try:
        # API anahtarlarını şifrele
        encrypted_api_key = encryption_service.encrypt(request.api_key)
        encrypted_api_secret = encryption_service.encrypt(request.api_secret)
        
        # Firebase'e kaydet
        await firebase_manager.save_api_keys(
            request.uid,
            encrypted_api_key,
            encrypted_api_secret
        )
        return JSONResponse(content={"success": True, "message": "API anahtarları başarıyla kaydedildi."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

# Firebase config'i frontend'e sunma endpoint'i
@app.get("/firebase-config")
async def get_firebase_config():
    config = {
        "apiKey": settings.FIREBASE_WEB_API_KEY,
        "authDomain": settings.FIREBASE_WEB_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_WEB_PROJECT_ID,
        "storageBucket": settings.FIREBASE_WEB_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_WEB_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_WEB_APP_ID
    }
    return JSONResponse(content=config)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
