# app/main.py - TAMAMEN DÜZELTİLMİŞ VERSİYON

import asyncio
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .bot_core import bot_core
from .config import settings
from .firebase_manager import firebase_manager

bearer_scheme = HTTPBearer()

# Rate limiting için basit bir sistem
class RateLimiter:
    def __init__(self, max_requests: int = 60, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}
    
    def is_allowed(self, client_id: str) -> bool:
        current_time = time.time()
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Eski istekleri temizle
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id] 
            if current_time - req_time < self.time_window
        ]
        
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(current_time)
        return True

rate_limiter = RateLimiter(max_requests=30, time_window=60)

async def authenticate(token: str = Depends(bearer_scheme)):
    """Gelen Firebase ID Token'ını doğrular ve rate limiting uygular."""
    user = firebase_manager.verify_token(token.credentials)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Geçersiz veya süresi dolmuş güvenlik token'ı.",
        )
    
    # Rate limiting kontrolü
    user_id = user.get('uid', 'unknown')
    if not rate_limiter.is_allowed(user_id):
        raise HTTPException(
            status_code=429,
            detail="Çok fazla istek. Lütfen bekleyin."
        )
    
    print(f"Doğrulanan kullanıcı: {user.get('email')}")
    return user

app = FastAPI(title="Binance Futures Bot", version="2.2.0")

@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında ayarları doğrula"""
    print("🚀 Bot başlatılıyor...")
    settings.validate_settings()
    settings.print_settings()

@app.on_event("shutdown")
async def shutdown_event():
    if bot_core.status["is_running"]:
        await bot_core.stop()

class StartRequest(BaseModel):
    symbol: str

class SymbolRequest(BaseModel):
    symbol: str

# ============ MEVCUT ENDPOINT'LER ============

@app.post("/api/start")
async def start_bot(request: StartRequest, background_tasks: BackgroundTasks, user: dict = Depends(authenticate)):
    if bot_core.status["is_running"]:
        raise HTTPException(status_code=400, detail="Bot zaten çalışıyor.")
    
    symbol = request.symbol.upper().strip()
    
    if not symbol.endswith('USDT'):
        symbol += 'USDT'
    
    if len(symbol) < 6 or len(symbol) > 20:
        raise HTTPException(status_code=400, detail="Geçersiz sembol formatı.")
    
    print(f"👤 {user.get('email')} tarafından bot başlatılıyor: {symbol}")
    
    background_tasks.add_task(bot_core.start, symbol)
    await asyncio.sleep(1.5)
    return bot_core.status

@app.post("/api/stop")
async def stop_bot(user: dict = Depends(authenticate)):
    if not bot_core.status["is_running"]:
        raise HTTPException(status_code=400, detail="Bot zaten durdurulmuş.")
    
    print(f"👤 {user.get('email')} tarafından bot durduruluyor")
    await bot_core.stop()
    return bot_core.status

@app.get("/api/status")
async def get_status(user: dict = Depends(authenticate)):
    return bot_core.status

@app.get("/api/health")
async def health_check():
    """Sağlık kontrolü - authentication gerektirmez"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "bot_running": bot_core.status["is_running"],
        "version": "2.2.0"
    }

# ============ YENİ ENDPOINT'LER - TEMİZLENMİŞ ============

@app.get("/api/payment-info")
async def get_payment_info():
    """Ödeme bilgilerini döndürür"""
    return {
        "success": True,
        "amount": "15",
        "trc20Address": "TMjSDNto6hoHUV9udDcXVAtuxxX6cnhhv3",
        "botPriceUsd": "15"
    }

# ============ STATIC FILES ============

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')
