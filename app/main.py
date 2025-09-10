from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator
import firebase_admin
from firebase_admin import credentials, firestore
import bcrypt
import jwt
from cryptography.fernet import Fernet
from contextlib import asynccontextmanager
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic Models
class UserRegistration(BaseModel):
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore
import bcrypt
import jwt
from cryptography.fernet import Fernet
import os
from contextlib import asynccontextmanager

# Pydantic Models
class UserRegistration(BaseModel):
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: str
    password: str

class TradingSettings(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z]{3,10}USDT$')
    timeframe: str = Field(..., regex=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)$')
    leverage: int = Field(default=5, ge=1, le=125)
    order_size_usdt: float = Field(default=35.0, ge=10.0, le=10000.0)
    stop_loss_percent: float = Field(..., ge=0.1, le=50.0)
    take_profit_percent: float = Field(..., ge=0.1, le=100.0)
    margin_type: str = Field(default="isolated", regex=r'^(isolated|cross)$')
    
    @validator('take_profit_percent')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss_percent' in values and v <= values['stop_loss_percent']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

class APIKeys(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)

class BotAction(BaseModel):
    action: str = Field(..., regex=r'^(start|stop)$')

# Global Variables
app = FastAPI(title="EzyagoTrading Bot", version="2.0.0")
security = HTTPBearer()
connected_websockets: Dict[str, WebSocket] = {}
bot_instances: Dict[str, 'TradingBot'] = {}

# Encryption setup
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# JWT Settings
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_firebase()
    await initialize_bot_manager()
    yield
    # Shutdown
    await cleanup_bots()

app = FastAPI(title="EzyagoTrading Bot", version="2.0.0", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da spesifik domain'ler ekleyin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility Functions
def encrypt_data(data: str) -> str:
    """Veriyi şifreler"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Şifrelenmiş veriyi çözer"""
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except:
        return ""

def create_jwt_token(user_id: str, email: str) -> str:
    """JWT token oluşturur"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[Dict]:
    """JWT token doğrular"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mevcut kullanıcıyı döndürür"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return payload

def check_subscription_status(user_id: str) -> bool:
    """Kullanıcının abonelik durumunu kontrol eder"""
    db = firestore.client()
    user_doc = db.collection('users').document(user_id).get()
    
    if not user_doc.exists:
        return False
    
    user_data = user_doc.to_dict()
    subscription_end = user_data.get('subscription_end')
    
    if not subscription_end:
        return False
    
    return subscription_end > datetime.utcnow()

def require_active_subscription(user: dict = Depends(get_current_user)):
    """Aktif abonelik gerektirir"""
    if not check_subscription_status(user['user_id']):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required"
        )
    return user

# Firebase Initialization
async def initialize_firebase():
    """Firebase'i başlatır"""
    try:
        # Firebase credentials from environment
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            # Fallback to environment variable
            cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
            else:
                raise ValueError("Firebase credentials not found")
        
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        raise

# Authentication Endpoints
@app.post("/api/auth/register")
async def register_user(user_data: UserRegistration):
    """Kullanıcı kaydı"""
    try:
        db = firestore.client()
        
        # Email kontrolü
        existing_user = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Şifre hash'leme
        password_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt())
        
        # Kullanıcı oluşturma
        user_doc = {
            'email': user_data.email,
            'full_name': user_data.full_name,
            'password_hash': password_hash.decode(),
            'created_at': datetime.utcnow(),
            'subscription_start': datetime.utcnow(),
            'subscription_end': datetime.utcnow() + timedelta(days=7),  # 7 gün deneme
            'is_trial': True,
            'api_keys_set': False,
            'bot_active': False
        }
        
        user_ref = db.collection('users').add(user_doc)
        user_id = user_ref[1].id
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "trial_days_left": 7
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/api/auth/login")
async def login_user(user_data: UserLogin):
    """Kullanıcı girişi"""
    try:
        db = firestore.client()
        
        # Kullanıcı bulma
        users = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user_doc = users[0]
        user_dict = user_doc.to_dict()
        user_id = user_doc.id
        
        # Şifre kontrolü
        if not bcrypt.checkpw(user_data.password.encode(), user_dict['password_hash'].encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        if user_dict.get('is_trial', False):
            subscription_end = user_dict.get('subscription_end')
            if subscription_end:
                remaining = subscription_end - datetime.utcnow()
                trial_days_left = max(0, remaining.days)
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_dict['email'],
                "full_name": user_dict['full_name'],
                "api_keys_set": user_dict.get('api_keys_set', False),
                "bot_active": user_dict.get('bot_active', False),
                "is_trial": user_dict.get('is_trial', False),
                "trial_days_left": trial_days_left
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

# API Key Management
@app.post("/api/user/api-keys")
async def save_api_keys(api_keys: APIKeys, user: dict = Depends(get_current_user)):
    """API anahtarlarını kaydeder"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        
        # API anahtarlarını şifrele
        encrypted_api_key = encrypt_data(api_keys.api_key)
        encrypted_api_secret = encrypt_data(api_keys.api_secret)
        
        # Veritabanına kaydet
        user_ref.update({
            'api_key': encrypted_api_key,
            'api_secret': encrypted_api_secret,
            'api_keys_set': True,
            'updated_at': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "API keys saved securely"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save API keys: {str(e)}"
        )

@app.get("/api/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Kullanıcı profil bilgileri"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        subscription_active = False
        
        if user_data.get('subscription_end'):
            remaining = user_data['subscription_end'] - datetime.utcnow()
            if remaining.total_seconds() > 0:
                subscription_active = True
                if user_data.get('is_trial', False):
                    trial_days_left = remaining.days
        
        return {
            "id": user['user_id'],
            "email": user_data['email'],
            "full_name": user_data['full_name'],
            "api_keys_set": user_data.get('api_keys_set', False),
            "bot_active": user_data.get('bot_active', False),
            "is_trial": user_data.get('is_trial', False),
            "trial_days_left": trial_days_left,
            "subscription_active": subscription_active,
            "created_at": user_data['created_at'].isoformat() if user_data.get('created_at') else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )

# WebSocket for real-time updates
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket bağlantısı"""
    await websocket.accept()
    connected_websockets[user_id] = websocket
    
    try:
        while True:
            # Heartbeat için ping-pong
            await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }))
    except WebSocketDisconnect:
        if user_id in connected_websockets:
            del connected_websockets[user_id]

async def send_websocket_message(user_id: str, message: dict):
    """WebSocket üzerinden mesaj gönderir"""
    if user_id in connected_websockets:
        try:
            await connected_websockets[user_id].send_text(json.dumps(message))
        except:
            # Bağlantı kopmuşsa listeden çıkar
            if user_id in connected_websockets:
                del connected_websockets[user_id]

# Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Ana sayfa"""
    return FileResponse("static/index.html")

# Health Check
@app.get("/api/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(connected_websockets),
        "active_bots": len(bot_instances)
    }

# Bot Management Endpoints
@app.post("/api/bot/start")
async def start_bot(settings: TradingSettings, user: dict = Depends(require_active_subscription)):
    """Botu başlatır"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # API anahtarlarını kontrol et
        if not user_data.get('api_keys_set', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please set your API keys first"
            )
        
        # API anahtarlarını çöz
        api_key = decrypt_data(user_data.get('api_key', ''))
        api_secret = decrypt_data(user_data.get('api_secret', ''))
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API keys"
            )
        
        # Trading settings oluştur
        from trading_bot import TradingSettings as BotTradingSettings, bot_manager
        
        bot_settings = BotTradingSettings(
            symbol=settings.symbol,
            timeframe=settings.timeframe,
            leverage=settings.leverage,
            order_size_usdt=settings.order_size_usdt,
            stop_loss_percent=settings.stop_loss_percent,
            take_profit_percent=settings.take_profit_percent,
            margin_type=settings.margin_type,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Botu başlat
        result = await bot_manager.start_bot(
            user['user_id'], 
            bot_settings, 
            send_websocket_message
        )
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db.collection('users').document(user['user_id']).update({
                'bot_active': True,
                'bot_started_at': datetime.utcnow(),
                'current_symbol': settings.symbol
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start bot: {str(e)}"
        )

@app.post("/api/bot/stop")
async def stop_bot(user: dict = Depends(get_current_user)):
    """Botu durdurur"""
    try:
        from trading_bot import bot_manager
        
        result = await bot_manager.stop_bot(user['user_id'])
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db = firestore.client()
            db.collection('users').document(user['user_id']).update({
                'bot_active': False,
                'bot_stopped_at': datetime.utcnow()
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop bot: {str(e)}"
        )

@app.get("/api/bot/status")
async def get_bot_status(user: dict = Depends(get_current_user)):
    """Bot durumunu döndürür"""
    try:
        from trading_bot import bot_manager
        
        status = bot_manager.get_bot_status(user['user_id'])
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bot status: {str(e)}"
        )

@app.get("/api/market/symbols")
async def get_futures_symbols():
    """Futures sembollerini döndürür"""
    try:
        # Binance'den popüler USDT futures sembollerini al
        popular_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "SOLUSDT", "DOTUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT",
            "LINKUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "FILUSDT",
            "TRXUSDT", "XLMUSDT", "VETUSDT", "ICPUSDT", "THETAUSDT"
        ]
        
        return {
            "success": True,
            "symbols": popular_symbols
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get symbols: {str(e)}"
        )

@app.get("/api/market/price/{symbol}")
async def get_symbol_price(symbol: str):
    """Sembol fiyatını döndürür"""
    try:
        # Bu endpoint gerçek zamanlı fiyat için Binance API'si kullanabilir
        # Şimdilik basit bir response döndürüyoruz
        return {
            "success": True,
            "symbol": symbol,
            "price": "0.00",
            "change_24h": "0.00",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get price: {str(e)}"
        )

# Trading History
@app.get("/api/trading/history")
async def get_trading_history(user: dict = Depends(get_current_user)):
    """Kullanıcının trading geçmişini döndürür"""
    try:
        db = firestore.client()
        
        # Son 30 günün işlemlerini al
        trades = db.collection('trades')\
                  .where('user_id', '==', user['user_id'])\
                  .order_by('created_at', direction=firestore.Query.DESCENDING)\
                  .limit(100)\
                  .get()
        
        trade_list = []
        for trade in trades:
            trade_data = trade.to_dict()
            trade_data['id'] = trade.id
            trade_list.append(trade_data)
        
        return {
            "success": True,
            "trades": trade_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trading history: {str(e)}"
        )

# Subscription Management
@app.post("/api/subscription/extend")
async def extend_subscription(days: int, user: dict = Depends(get_current_user)):
    """Aboneliği uzatır (admin veya ödeme sonrası)"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        current_end = user_data.get('subscription_end', datetime.utcnow())
        
        # Eğer abonelik bitmiş ise bugünden başlat, değilse mevcut bitiş tarihine ekle
        if current_end < datetime.utcnow():
            new_end = datetime.utcnow() + timedelta(days=days)
        else:
            new_end = current_end + timedelta(days=days)
        
        user_ref.update({
            'subscription_end': new_end,
            'is_trial': False,
            'last_payment': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Subscription extended by {days} days",
            "new_end_date": new_end.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend subscription: {str(e)}"
        )

# Bot Management Functions
async def initialize_bot_manager():
    """Bot yöneticisini başlatır"""
    from trading_bot import bot_manager
    print("✅ Bot manager initialized")

async def cleanup_bots():
    """Tüm botları güvenli şekilde kapatır"""
    from trading_bot import bot_manager
    await bot_manager.stop_all_bots()
    print("✅ All bots stopped safely")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ))
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: str
    password: str

class TradingSettings(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z]{3,10}USDTfrom fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore
import bcrypt
import jwt
from cryptography.fernet import Fernet
import os
from contextlib import asynccontextmanager

# Pydantic Models
class UserRegistration(BaseModel):
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: str
    password: str

class TradingSettings(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z]{3,10}USDT$')
    timeframe: str = Field(..., regex=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)$')
    leverage: int = Field(default=5, ge=1, le=125)
    order_size_usdt: float = Field(default=35.0, ge=10.0, le=10000.0)
    stop_loss_percent: float = Field(..., ge=0.1, le=50.0)
    take_profit_percent: float = Field(..., ge=0.1, le=100.0)
    margin_type: str = Field(default="isolated", regex=r'^(isolated|cross)$')
    
    @validator('take_profit_percent')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss_percent' in values and v <= values['stop_loss_percent']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

class APIKeys(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)

class BotAction(BaseModel):
    action: str = Field(..., regex=r'^(start|stop)$')

# Global Variables
app = FastAPI(title="EzyagoTrading Bot", version="2.0.0")
security = HTTPBearer()
connected_websockets: Dict[str, WebSocket] = {}
bot_instances: Dict[str, 'TradingBot'] = {}

# Encryption setup
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# JWT Settings
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_firebase()
    await initialize_bot_manager()
    yield
    # Shutdown
    await cleanup_bots()

app = FastAPI(title="EzyagoTrading Bot", version="2.0.0", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da spesifik domain'ler ekleyin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility Functions
def encrypt_data(data: str) -> str:
    """Veriyi şifreler"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Şifrelenmiş veriyi çözer"""
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except:
        return ""

def create_jwt_token(user_id: str, email: str) -> str:
    """JWT token oluşturur"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[Dict]:
    """JWT token doğrular"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mevcut kullanıcıyı döndürür"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return payload

def check_subscription_status(user_id: str) -> bool:
    """Kullanıcının abonelik durumunu kontrol eder"""
    db = firestore.client()
    user_doc = db.collection('users').document(user_id).get()
    
    if not user_doc.exists:
        return False
    
    user_data = user_doc.to_dict()
    subscription_end = user_data.get('subscription_end')
    
    if not subscription_end:
        return False
    
    return subscription_end > datetime.utcnow()

def require_active_subscription(user: dict = Depends(get_current_user)):
    """Aktif abonelik gerektirir"""
    if not check_subscription_status(user['user_id']):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required"
        )
    return user

# Firebase Initialization
async def initialize_firebase():
    """Firebase'i başlatır"""
    try:
        # Firebase credentials from environment
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            # Fallback to environment variable
            cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
            else:
                raise ValueError("Firebase credentials not found")
        
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        raise

# Authentication Endpoints
@app.post("/api/auth/register")
async def register_user(user_data: UserRegistration):
    """Kullanıcı kaydı"""
    try:
        db = firestore.client()
        
        # Email kontrolü
        existing_user = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Şifre hash'leme
        password_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt())
        
        # Kullanıcı oluşturma
        user_doc = {
            'email': user_data.email,
            'full_name': user_data.full_name,
            'password_hash': password_hash.decode(),
            'created_at': datetime.utcnow(),
            'subscription_start': datetime.utcnow(),
            'subscription_end': datetime.utcnow() + timedelta(days=7),  # 7 gün deneme
            'is_trial': True,
            'api_keys_set': False,
            'bot_active': False
        }
        
        user_ref = db.collection('users').add(user_doc)
        user_id = user_ref[1].id
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "trial_days_left": 7
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/api/auth/login")
async def login_user(user_data: UserLogin):
    """Kullanıcı girişi"""
    try:
        db = firestore.client()
        
        # Kullanıcı bulma
        users = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user_doc = users[0]
        user_dict = user_doc.to_dict()
        user_id = user_doc.id
        
        # Şifre kontrolü
        if not bcrypt.checkpw(user_data.password.encode(), user_dict['password_hash'].encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        if user_dict.get('is_trial', False):
            subscription_end = user_dict.get('subscription_end')
            if subscription_end:
                remaining = subscription_end - datetime.utcnow()
                trial_days_left = max(0, remaining.days)
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_dict['email'],
                "full_name": user_dict['full_name'],
                "api_keys_set": user_dict.get('api_keys_set', False),
                "bot_active": user_dict.get('bot_active', False),
                "is_trial": user_dict.get('is_trial', False),
                "trial_days_left": trial_days_left
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

# API Key Management
@app.post("/api/user/api-keys")
async def save_api_keys(api_keys: APIKeys, user: dict = Depends(get_current_user)):
    """API anahtarlarını kaydeder"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        
        # API anahtarlarını şifrele
        encrypted_api_key = encrypt_data(api_keys.api_key)
        encrypted_api_secret = encrypt_data(api_keys.api_secret)
        
        # Veritabanına kaydet
        user_ref.update({
            'api_key': encrypted_api_key,
            'api_secret': encrypted_api_secret,
            'api_keys_set': True,
            'updated_at': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "API keys saved securely"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save API keys: {str(e)}"
        )

@app.get("/api/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Kullanıcı profil bilgileri"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        subscription_active = False
        
        if user_data.get('subscription_end'):
            remaining = user_data['subscription_end'] - datetime.utcnow()
            if remaining.total_seconds() > 0:
                subscription_active = True
                if user_data.get('is_trial', False):
                    trial_days_left = remaining.days
        
        return {
            "id": user['user_id'],
            "email": user_data['email'],
            "full_name": user_data['full_name'],
            "api_keys_set": user_data.get('api_keys_set', False),
            "bot_active": user_data.get('bot_active', False),
            "is_trial": user_data.get('is_trial', False),
            "trial_days_left": trial_days_left,
            "subscription_active": subscription_active,
            "created_at": user_data['created_at'].isoformat() if user_data.get('created_at') else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )

# WebSocket for real-time updates
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket bağlantısı"""
    await websocket.accept()
    connected_websockets[user_id] = websocket
    
    try:
        while True:
            # Heartbeat için ping-pong
            await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }))
    except WebSocketDisconnect:
        if user_id in connected_websockets:
            del connected_websockets[user_id]

async def send_websocket_message(user_id: str, message: dict):
    """WebSocket üzerinden mesaj gönderir"""
    if user_id in connected_websockets:
        try:
            await connected_websockets[user_id].send_text(json.dumps(message))
        except:
            # Bağlantı kopmuşsa listeden çıkar
            if user_id in connected_websockets:
                del connected_websockets[user_id]

# Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Ana sayfa"""
    return FileResponse("static/index.html")

# Health Check
@app.get("/api/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(connected_websockets),
        "active_bots": len(bot_instances)
    }

# Bot Management Endpoints
@app.post("/api/bot/start")
async def start_bot(settings: TradingSettings, user: dict = Depends(require_active_subscription)):
    """Botu başlatır"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # API anahtarlarını kontrol et
        if not user_data.get('api_keys_set', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please set your API keys first"
            )
        
        # API anahtarlarını çöz
        api_key = decrypt_data(user_data.get('api_key', ''))
        api_secret = decrypt_data(user_data.get('api_secret', ''))
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API keys"
            )
        
        # Trading settings oluştur
        from trading_bot import TradingSettings as BotTradingSettings, bot_manager
        
        bot_settings = BotTradingSettings(
            symbol=settings.symbol,
            timeframe=settings.timeframe,
            leverage=settings.leverage,
            order_size_usdt=settings.order_size_usdt,
            stop_loss_percent=settings.stop_loss_percent,
            take_profit_percent=settings.take_profit_percent,
            margin_type=settings.margin_type,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Botu başlat
        result = await bot_manager.start_bot(
            user['user_id'], 
            bot_settings, 
            send_websocket_message
        )
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db.collection('users').document(user['user_id']).update({
                'bot_active': True,
                'bot_started_at': datetime.utcnow(),
                'current_symbol': settings.symbol
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start bot: {str(e)}"
        )

@app.post("/api/bot/stop")
async def stop_bot(user: dict = Depends(get_current_user)):
    """Botu durdurur"""
    try:
        from trading_bot import bot_manager
        
        result = await bot_manager.stop_bot(user['user_id'])
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db = firestore.client()
            db.collection('users').document(user['user_id']).update({
                'bot_active': False,
                'bot_stopped_at': datetime.utcnow()
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop bot: {str(e)}"
        )

@app.get("/api/bot/status")
async def get_bot_status(user: dict = Depends(get_current_user)):
    """Bot durumunu döndürür"""
    try:
        from trading_bot import bot_manager
        
        status = bot_manager.get_bot_status(user['user_id'])
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bot status: {str(e)}"
        )

@app.get("/api/market/symbols")
async def get_futures_symbols():
    """Futures sembollerini döndürür"""
    try:
        # Binance'den popüler USDT futures sembollerini al
        popular_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "SOLUSDT", "DOTUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT",
            "LINKUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "FILUSDT",
            "TRXUSDT", "XLMUSDT", "VETUSDT", "ICPUSDT", "THETAUSDT"
        ]
        
        return {
            "success": True,
            "symbols": popular_symbols
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get symbols: {str(e)}"
        )

@app.get("/api/market/price/{symbol}")
async def get_symbol_price(symbol: str):
    """Sembol fiyatını döndürür"""
    try:
        # Bu endpoint gerçek zamanlı fiyat için Binance API'si kullanabilir
        # Şimdilik basit bir response döndürüyoruz
        return {
            "success": True,
            "symbol": symbol,
            "price": "0.00",
            "change_24h": "0.00",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get price: {str(e)}"
        )

# Trading History
@app.get("/api/trading/history")
async def get_trading_history(user: dict = Depends(get_current_user)):
    """Kullanıcının trading geçmişini döndürür"""
    try:
        db = firestore.client()
        
        # Son 30 günün işlemlerini al
        trades = db.collection('trades')\
                  .where('user_id', '==', user['user_id'])\
                  .order_by('created_at', direction=firestore.Query.DESCENDING)\
                  .limit(100)\
                  .get()
        
        trade_list = []
        for trade in trades:
            trade_data = trade.to_dict()
            trade_data['id'] = trade.id
            trade_list.append(trade_data)
        
        return {
            "success": True,
            "trades": trade_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trading history: {str(e)}"
        )

# Subscription Management
@app.post("/api/subscription/extend")
async def extend_subscription(days: int, user: dict = Depends(get_current_user)):
    """Aboneliği uzatır (admin veya ödeme sonrası)"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        current_end = user_data.get('subscription_end', datetime.utcnow())
        
        # Eğer abonelik bitmiş ise bugünden başlat, değilse mevcut bitiş tarihine ekle
        if current_end < datetime.utcnow():
            new_end = datetime.utcnow() + timedelta(days=days)
        else:
            new_end = current_end + timedelta(days=days)
        
        user_ref.update({
            'subscription_end': new_end,
            'is_trial': False,
            'last_payment': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Subscription extended by {days} days",
            "new_end_date": new_end.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend subscription: {str(e)}"
        )

# Bot Management Functions
async def initialize_bot_manager():
    """Bot yöneticisini başlatır"""
    from trading_bot import bot_manager
    print("✅ Bot manager initialized")

async def cleanup_bots():
    """Tüm botları güvenli şekilde kapatır"""
    from trading_bot import bot_manager
    await bot_manager.stop_all_bots()
    print("✅ All bots stopped safely")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ))
    timeframe: str = Field(..., regex=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore
import bcrypt
import jwt
from cryptography.fernet import Fernet
import os
from contextlib import asynccontextmanager

# Pydantic Models
class UserRegistration(BaseModel):
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: str
    password: str

class TradingSettings(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z]{3,10}USDT$')
    timeframe: str = Field(..., regex=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)$')
    leverage: int = Field(default=5, ge=1, le=125)
    order_size_usdt: float = Field(default=35.0, ge=10.0, le=10000.0)
    stop_loss_percent: float = Field(..., ge=0.1, le=50.0)
    take_profit_percent: float = Field(..., ge=0.1, le=100.0)
    margin_type: str = Field(default="isolated", regex=r'^(isolated|cross)$')
    
    @validator('take_profit_percent')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss_percent' in values and v <= values['stop_loss_percent']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

class APIKeys(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)

class BotAction(BaseModel):
    action: str = Field(..., regex=r'^(start|stop)$')

# Global Variables
app = FastAPI(title="EzyagoTrading Bot", version="2.0.0")
security = HTTPBearer()
connected_websockets: Dict[str, WebSocket] = {}
bot_instances: Dict[str, 'TradingBot'] = {}

# Encryption setup
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# JWT Settings
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_firebase()
    await initialize_bot_manager()
    yield
    # Shutdown
    await cleanup_bots()

app = FastAPI(title="EzyagoTrading Bot", version="2.0.0", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da spesifik domain'ler ekleyin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility Functions
def encrypt_data(data: str) -> str:
    """Veriyi şifreler"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Şifrelenmiş veriyi çözer"""
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except:
        return ""

def create_jwt_token(user_id: str, email: str) -> str:
    """JWT token oluşturur"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[Dict]:
    """JWT token doğrular"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mevcut kullanıcıyı döndürür"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return payload

def check_subscription_status(user_id: str) -> bool:
    """Kullanıcının abonelik durumunu kontrol eder"""
    db = firestore.client()
    user_doc = db.collection('users').document(user_id).get()
    
    if not user_doc.exists:
        return False
    
    user_data = user_doc.to_dict()
    subscription_end = user_data.get('subscription_end')
    
    if not subscription_end:
        return False
    
    return subscription_end > datetime.utcnow()

def require_active_subscription(user: dict = Depends(get_current_user)):
    """Aktif abonelik gerektirir"""
    if not check_subscription_status(user['user_id']):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required"
        )
    return user

# Firebase Initialization
async def initialize_firebase():
    """Firebase'i başlatır"""
    try:
        # Firebase credentials from environment
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            # Fallback to environment variable
            cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
            else:
                raise ValueError("Firebase credentials not found")
        
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        raise

# Authentication Endpoints
@app.post("/api/auth/register")
async def register_user(user_data: UserRegistration):
    """Kullanıcı kaydı"""
    try:
        db = firestore.client()
        
        # Email kontrolü
        existing_user = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Şifre hash'leme
        password_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt())
        
        # Kullanıcı oluşturma
        user_doc = {
            'email': user_data.email,
            'full_name': user_data.full_name,
            'password_hash': password_hash.decode(),
            'created_at': datetime.utcnow(),
            'subscription_start': datetime.utcnow(),
            'subscription_end': datetime.utcnow() + timedelta(days=7),  # 7 gün deneme
            'is_trial': True,
            'api_keys_set': False,
            'bot_active': False
        }
        
        user_ref = db.collection('users').add(user_doc)
        user_id = user_ref[1].id
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "trial_days_left": 7
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/api/auth/login")
async def login_user(user_data: UserLogin):
    """Kullanıcı girişi"""
    try:
        db = firestore.client()
        
        # Kullanıcı bulma
        users = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user_doc = users[0]
        user_dict = user_doc.to_dict()
        user_id = user_doc.id
        
        # Şifre kontrolü
        if not bcrypt.checkpw(user_data.password.encode(), user_dict['password_hash'].encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        if user_dict.get('is_trial', False):
            subscription_end = user_dict.get('subscription_end')
            if subscription_end:
                remaining = subscription_end - datetime.utcnow()
                trial_days_left = max(0, remaining.days)
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_dict['email'],
                "full_name": user_dict['full_name'],
                "api_keys_set": user_dict.get('api_keys_set', False),
                "bot_active": user_dict.get('bot_active', False),
                "is_trial": user_dict.get('is_trial', False),
                "trial_days_left": trial_days_left
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

# API Key Management
@app.post("/api/user/api-keys")
async def save_api_keys(api_keys: APIKeys, user: dict = Depends(get_current_user)):
    """API anahtarlarını kaydeder"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        
        # API anahtarlarını şifrele
        encrypted_api_key = encrypt_data(api_keys.api_key)
        encrypted_api_secret = encrypt_data(api_keys.api_secret)
        
        # Veritabanına kaydet
        user_ref.update({
            'api_key': encrypted_api_key,
            'api_secret': encrypted_api_secret,
            'api_keys_set': True,
            'updated_at': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "API keys saved securely"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save API keys: {str(e)}"
        )

@app.get("/api/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Kullanıcı profil bilgileri"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        subscription_active = False
        
        if user_data.get('subscription_end'):
            remaining = user_data['subscription_end'] - datetime.utcnow()
            if remaining.total_seconds() > 0:
                subscription_active = True
                if user_data.get('is_trial', False):
                    trial_days_left = remaining.days
        
        return {
            "id": user['user_id'],
            "email": user_data['email'],
            "full_name": user_data['full_name'],
            "api_keys_set": user_data.get('api_keys_set', False),
            "bot_active": user_data.get('bot_active', False),
            "is_trial": user_data.get('is_trial', False),
            "trial_days_left": trial_days_left,
            "subscription_active": subscription_active,
            "created_at": user_data['created_at'].isoformat() if user_data.get('created_at') else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )

# WebSocket for real-time updates
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket bağlantısı"""
    await websocket.accept()
    connected_websockets[user_id] = websocket
    
    try:
        while True:
            # Heartbeat için ping-pong
            await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }))
    except WebSocketDisconnect:
        if user_id in connected_websockets:
            del connected_websockets[user_id]

async def send_websocket_message(user_id: str, message: dict):
    """WebSocket üzerinden mesaj gönderir"""
    if user_id in connected_websockets:
        try:
            await connected_websockets[user_id].send_text(json.dumps(message))
        except:
            # Bağlantı kopmuşsa listeden çıkar
            if user_id in connected_websockets:
                del connected_websockets[user_id]

# Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Ana sayfa"""
    return FileResponse("static/index.html")

# Health Check
@app.get("/api/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(connected_websockets),
        "active_bots": len(bot_instances)
    }

# Bot Management Endpoints
@app.post("/api/bot/start")
async def start_bot(settings: TradingSettings, user: dict = Depends(require_active_subscription)):
    """Botu başlatır"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # API anahtarlarını kontrol et
        if not user_data.get('api_keys_set', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please set your API keys first"
            )
        
        # API anahtarlarını çöz
        api_key = decrypt_data(user_data.get('api_key', ''))
        api_secret = decrypt_data(user_data.get('api_secret', ''))
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API keys"
            )
        
        # Trading settings oluştur
        from trading_bot import TradingSettings as BotTradingSettings, bot_manager
        
        bot_settings = BotTradingSettings(
            symbol=settings.symbol,
            timeframe=settings.timeframe,
            leverage=settings.leverage,
            order_size_usdt=settings.order_size_usdt,
            stop_loss_percent=settings.stop_loss_percent,
            take_profit_percent=settings.take_profit_percent,
            margin_type=settings.margin_type,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Botu başlat
        result = await bot_manager.start_bot(
            user['user_id'], 
            bot_settings, 
            send_websocket_message
        )
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db.collection('users').document(user['user_id']).update({
                'bot_active': True,
                'bot_started_at': datetime.utcnow(),
                'current_symbol': settings.symbol
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start bot: {str(e)}"
        )

@app.post("/api/bot/stop")
async def stop_bot(user: dict = Depends(get_current_user)):
    """Botu durdurur"""
    try:
        from trading_bot import bot_manager
        
        result = await bot_manager.stop_bot(user['user_id'])
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db = firestore.client()
            db.collection('users').document(user['user_id']).update({
                'bot_active': False,
                'bot_stopped_at': datetime.utcnow()
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop bot: {str(e)}"
        )

@app.get("/api/bot/status")
async def get_bot_status(user: dict = Depends(get_current_user)):
    """Bot durumunu döndürür"""
    try:
        from trading_bot import bot_manager
        
        status = bot_manager.get_bot_status(user['user_id'])
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bot status: {str(e)}"
        )

@app.get("/api/market/symbols")
async def get_futures_symbols():
    """Futures sembollerini döndürür"""
    try:
        # Binance'den popüler USDT futures sembollerini al
        popular_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "SOLUSDT", "DOTUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT",
            "LINKUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "FILUSDT",
            "TRXUSDT", "XLMUSDT", "VETUSDT", "ICPUSDT", "THETAUSDT"
        ]
        
        return {
            "success": True,
            "symbols": popular_symbols
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get symbols: {str(e)}"
        )

@app.get("/api/market/price/{symbol}")
async def get_symbol_price(symbol: str):
    """Sembol fiyatını döndürür"""
    try:
        # Bu endpoint gerçek zamanlı fiyat için Binance API'si kullanabilir
        # Şimdilik basit bir response döndürüyoruz
        return {
            "success": True,
            "symbol": symbol,
            "price": "0.00",
            "change_24h": "0.00",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get price: {str(e)}"
        )

# Trading History
@app.get("/api/trading/history")
async def get_trading_history(user: dict = Depends(get_current_user)):
    """Kullanıcının trading geçmişini döndürür"""
    try:
        db = firestore.client()
        
        # Son 30 günün işlemlerini al
        trades = db.collection('trades')\
                  .where('user_id', '==', user['user_id'])\
                  .order_by('created_at', direction=firestore.Query.DESCENDING)\
                  .limit(100)\
                  .get()
        
        trade_list = []
        for trade in trades:
            trade_data = trade.to_dict()
            trade_data['id'] = trade.id
            trade_list.append(trade_data)
        
        return {
            "success": True,
            "trades": trade_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trading history: {str(e)}"
        )

# Subscription Management
@app.post("/api/subscription/extend")
async def extend_subscription(days: int, user: dict = Depends(get_current_user)):
    """Aboneliği uzatır (admin veya ödeme sonrası)"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        current_end = user_data.get('subscription_end', datetime.utcnow())
        
        # Eğer abonelik bitmiş ise bugünden başlat, değilse mevcut bitiş tarihine ekle
        if current_end < datetime.utcnow():
            new_end = datetime.utcnow() + timedelta(days=days)
        else:
            new_end = current_end + timedelta(days=days)
        
        user_ref.update({
            'subscription_end': new_end,
            'is_trial': False,
            'last_payment': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Subscription extended by {days} days",
            "new_end_date": new_end.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend subscription: {str(e)}"
        )

# Bot Management Functions
async def initialize_bot_manager():
    """Bot yöneticisini başlatır"""
    from trading_bot import bot_manager
    print("✅ Bot manager initialized")

async def cleanup_bots():
    """Tüm botları güvenli şekilde kapatır"""
    from trading_bot import bot_manager
    await bot_manager.stop_all_bots()
    print("✅ All bots stopped safely")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ))
    leverage: int = Field(default=5, ge=1, le=125)
    order_size_usdt: float = Field(default=35.0, ge=10.0, le=10000.0)
    stop_loss_percent: float = Field(..., ge=0.1, le=50.0)
    take_profit_percent: float = Field(..., ge=0.1, le=100.0)
    margin_type: str = Field(default="isolated", regex=r'^(isolated|cross)from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore
import bcrypt
import jwt
from cryptography.fernet import Fernet
import os
from contextlib import asynccontextmanager

# Pydantic Models
class UserRegistration(BaseModel):
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: str
    password: str

class TradingSettings(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z]{3,10}USDT$')
    timeframe: str = Field(..., regex=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)$')
    leverage: int = Field(default=5, ge=1, le=125)
    order_size_usdt: float = Field(default=35.0, ge=10.0, le=10000.0)
    stop_loss_percent: float = Field(..., ge=0.1, le=50.0)
    take_profit_percent: float = Field(..., ge=0.1, le=100.0)
    margin_type: str = Field(default="isolated", regex=r'^(isolated|cross)$')
    
    @validator('take_profit_percent')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss_percent' in values and v <= values['stop_loss_percent']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

class APIKeys(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)

class BotAction(BaseModel):
    action: str = Field(..., regex=r'^(start|stop)$')

# Global Variables
app = FastAPI(title="EzyagoTrading Bot", version="2.0.0")
security = HTTPBearer()
connected_websockets: Dict[str, WebSocket] = {}
bot_instances: Dict[str, 'TradingBot'] = {}

# Encryption setup
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# JWT Settings
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_firebase()
    await initialize_bot_manager()
    yield
    # Shutdown
    await cleanup_bots()

app = FastAPI(title="EzyagoTrading Bot", version="2.0.0", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da spesifik domain'ler ekleyin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility Functions
def encrypt_data(data: str) -> str:
    """Veriyi şifreler"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Şifrelenmiş veriyi çözer"""
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except:
        return ""

def create_jwt_token(user_id: str, email: str) -> str:
    """JWT token oluşturur"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[Dict]:
    """JWT token doğrular"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mevcut kullanıcıyı döndürür"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return payload

def check_subscription_status(user_id: str) -> bool:
    """Kullanıcının abonelik durumunu kontrol eder"""
    db = firestore.client()
    user_doc = db.collection('users').document(user_id).get()
    
    if not user_doc.exists:
        return False
    
    user_data = user_doc.to_dict()
    subscription_end = user_data.get('subscription_end')
    
    if not subscription_end:
        return False
    
    return subscription_end > datetime.utcnow()

def require_active_subscription(user: dict = Depends(get_current_user)):
    """Aktif abonelik gerektirir"""
    if not check_subscription_status(user['user_id']):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required"
        )
    return user

# Firebase Initialization
async def initialize_firebase():
    """Firebase'i başlatır"""
    try:
        # Firebase credentials from environment
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            # Fallback to environment variable
            cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
            else:
                raise ValueError("Firebase credentials not found")
        
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        raise

# Authentication Endpoints
@app.post("/api/auth/register")
async def register_user(user_data: UserRegistration):
    """Kullanıcı kaydı"""
    try:
        db = firestore.client()
        
        # Email kontrolü
        existing_user = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Şifre hash'leme
        password_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt())
        
        # Kullanıcı oluşturma
        user_doc = {
            'email': user_data.email,
            'full_name': user_data.full_name,
            'password_hash': password_hash.decode(),
            'created_at': datetime.utcnow(),
            'subscription_start': datetime.utcnow(),
            'subscription_end': datetime.utcnow() + timedelta(days=7),  # 7 gün deneme
            'is_trial': True,
            'api_keys_set': False,
            'bot_active': False
        }
        
        user_ref = db.collection('users').add(user_doc)
        user_id = user_ref[1].id
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "trial_days_left": 7
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/api/auth/login")
async def login_user(user_data: UserLogin):
    """Kullanıcı girişi"""
    try:
        db = firestore.client()
        
        # Kullanıcı bulma
        users = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user_doc = users[0]
        user_dict = user_doc.to_dict()
        user_id = user_doc.id
        
        # Şifre kontrolü
        if not bcrypt.checkpw(user_data.password.encode(), user_dict['password_hash'].encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        if user_dict.get('is_trial', False):
            subscription_end = user_dict.get('subscription_end')
            if subscription_end:
                remaining = subscription_end - datetime.utcnow()
                trial_days_left = max(0, remaining.days)
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_dict['email'],
                "full_name": user_dict['full_name'],
                "api_keys_set": user_dict.get('api_keys_set', False),
                "bot_active": user_dict.get('bot_active', False),
                "is_trial": user_dict.get('is_trial', False),
                "trial_days_left": trial_days_left
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

# API Key Management
@app.post("/api/user/api-keys")
async def save_api_keys(api_keys: APIKeys, user: dict = Depends(get_current_user)):
    """API anahtarlarını kaydeder"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        
        # API anahtarlarını şifrele
        encrypted_api_key = encrypt_data(api_keys.api_key)
        encrypted_api_secret = encrypt_data(api_keys.api_secret)
        
        # Veritabanına kaydet
        user_ref.update({
            'api_key': encrypted_api_key,
            'api_secret': encrypted_api_secret,
            'api_keys_set': True,
            'updated_at': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "API keys saved securely"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save API keys: {str(e)}"
        )

@app.get("/api/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Kullanıcı profil bilgileri"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        subscription_active = False
        
        if user_data.get('subscription_end'):
            remaining = user_data['subscription_end'] - datetime.utcnow()
            if remaining.total_seconds() > 0:
                subscription_active = True
                if user_data.get('is_trial', False):
                    trial_days_left = remaining.days
        
        return {
            "id": user['user_id'],
            "email": user_data['email'],
            "full_name": user_data['full_name'],
            "api_keys_set": user_data.get('api_keys_set', False),
            "bot_active": user_data.get('bot_active', False),
            "is_trial": user_data.get('is_trial', False),
            "trial_days_left": trial_days_left,
            "subscription_active": subscription_active,
            "created_at": user_data['created_at'].isoformat() if user_data.get('created_at') else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )

# WebSocket for real-time updates
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket bağlantısı"""
    await websocket.accept()
    connected_websockets[user_id] = websocket
    
    try:
        while True:
            # Heartbeat için ping-pong
            await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }))
    except WebSocketDisconnect:
        if user_id in connected_websockets:
            del connected_websockets[user_id]

async def send_websocket_message(user_id: str, message: dict):
    """WebSocket üzerinden mesaj gönderir"""
    if user_id in connected_websockets:
        try:
            await connected_websockets[user_id].send_text(json.dumps(message))
        except:
            # Bağlantı kopmuşsa listeden çıkar
            if user_id in connected_websockets:
                del connected_websockets[user_id]

# Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Ana sayfa"""
    return FileResponse("static/index.html")

# Health Check
@app.get("/api/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(connected_websockets),
        "active_bots": len(bot_instances)
    }

# Bot Management Endpoints
@app.post("/api/bot/start")
async def start_bot(settings: TradingSettings, user: dict = Depends(require_active_subscription)):
    """Botu başlatır"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # API anahtarlarını kontrol et
        if not user_data.get('api_keys_set', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please set your API keys first"
            )
        
        # API anahtarlarını çöz
        api_key = decrypt_data(user_data.get('api_key', ''))
        api_secret = decrypt_data(user_data.get('api_secret', ''))
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API keys"
            )
        
        # Trading settings oluştur
        from trading_bot import TradingSettings as BotTradingSettings, bot_manager
        
        bot_settings = BotTradingSettings(
            symbol=settings.symbol,
            timeframe=settings.timeframe,
            leverage=settings.leverage,
            order_size_usdt=settings.order_size_usdt,
            stop_loss_percent=settings.stop_loss_percent,
            take_profit_percent=settings.take_profit_percent,
            margin_type=settings.margin_type,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Botu başlat
        result = await bot_manager.start_bot(
            user['user_id'], 
            bot_settings, 
            send_websocket_message
        )
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db.collection('users').document(user['user_id']).update({
                'bot_active': True,
                'bot_started_at': datetime.utcnow(),
                'current_symbol': settings.symbol
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start bot: {str(e)}"
        )

@app.post("/api/bot/stop")
async def stop_bot(user: dict = Depends(get_current_user)):
    """Botu durdurur"""
    try:
        from trading_bot import bot_manager
        
        result = await bot_manager.stop_bot(user['user_id'])
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db = firestore.client()
            db.collection('users').document(user['user_id']).update({
                'bot_active': False,
                'bot_stopped_at': datetime.utcnow()
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop bot: {str(e)}"
        )

@app.get("/api/bot/status")
async def get_bot_status(user: dict = Depends(get_current_user)):
    """Bot durumunu döndürür"""
    try:
        from trading_bot import bot_manager
        
        status = bot_manager.get_bot_status(user['user_id'])
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bot status: {str(e)}"
        )

@app.get("/api/market/symbols")
async def get_futures_symbols():
    """Futures sembollerini döndürür"""
    try:
        # Binance'den popüler USDT futures sembollerini al
        popular_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "SOLUSDT", "DOTUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT",
            "LINKUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "FILUSDT",
            "TRXUSDT", "XLMUSDT", "VETUSDT", "ICPUSDT", "THETAUSDT"
        ]
        
        return {
            "success": True,
            "symbols": popular_symbols
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get symbols: {str(e)}"
        )

@app.get("/api/market/price/{symbol}")
async def get_symbol_price(symbol: str):
    """Sembol fiyatını döndürür"""
    try:
        # Bu endpoint gerçek zamanlı fiyat için Binance API'si kullanabilir
        # Şimdilik basit bir response döndürüyoruz
        return {
            "success": True,
            "symbol": symbol,
            "price": "0.00",
            "change_24h": "0.00",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get price: {str(e)}"
        )

# Trading History
@app.get("/api/trading/history")
async def get_trading_history(user: dict = Depends(get_current_user)):
    """Kullanıcının trading geçmişini döndürür"""
    try:
        db = firestore.client()
        
        # Son 30 günün işlemlerini al
        trades = db.collection('trades')\
                  .where('user_id', '==', user['user_id'])\
                  .order_by('created_at', direction=firestore.Query.DESCENDING)\
                  .limit(100)\
                  .get()
        
        trade_list = []
        for trade in trades:
            trade_data = trade.to_dict()
            trade_data['id'] = trade.id
            trade_list.append(trade_data)
        
        return {
            "success": True,
            "trades": trade_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trading history: {str(e)}"
        )

# Subscription Management
@app.post("/api/subscription/extend")
async def extend_subscription(days: int, user: dict = Depends(get_current_user)):
    """Aboneliği uzatır (admin veya ödeme sonrası)"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        current_end = user_data.get('subscription_end', datetime.utcnow())
        
        # Eğer abonelik bitmiş ise bugünden başlat, değilse mevcut bitiş tarihine ekle
        if current_end < datetime.utcnow():
            new_end = datetime.utcnow() + timedelta(days=days)
        else:
            new_end = current_end + timedelta(days=days)
        
        user_ref.update({
            'subscription_end': new_end,
            'is_trial': False,
            'last_payment': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Subscription extended by {days} days",
            "new_end_date": new_end.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend subscription: {str(e)}"
        )

# Bot Management Functions
async def initialize_bot_manager():
    """Bot yöneticisini başlatır"""
    from trading_bot import bot_manager
    print("✅ Bot manager initialized")

async def cleanup_bots():
    """Tüm botları güvenli şekilde kapatır"""
    from trading_bot import bot_manager
    await bot_manager.stop_all_bots()
    print("✅ All bots stopped safely")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ))
    
    @validator('take_profit_percent')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss_percent' in values and v <= values['stop_loss_percent']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

class APIKeys(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)

# Global Variables
connected_websockets: Dict[str, WebSocket] = {}

# Environment Variables
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning("Generated new encryption key. Set ENCRYPTION_KEY environment variable for production!")

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# JWT Settings
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_firebase()
    await initialize_bot_manager()
    logger.info("🚀 EzyagoTrading started successfully!")
    yield
    # Shutdown
    await cleanup_bots()
    logger.info("👋 EzyagoTrading stopped gracefully!")

app = FastAPI(
    title="EzyagoTrading Bot", 
    version="2.0.0",
    description="Professional Crypto Futures Trading Bot",
    lifespan=lifespan
)

# CORS Middleware
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allowed_origins == ['*'] else allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Utility Functions
def encrypt_data(data: str) -> str:
    """Veriyi şifreler"""
    if not data:
        return ""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Şifrelenmiş veriyi çözer"""
    if not encrypted_data:
        return ""
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return ""

def create_jwt_token(user_id: str, email: str) -> str:
    """JWT token oluşturur"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[Dict]:
    """JWT token doğrular"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mevcut kullanıcıyı döndürür"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

def check_subscription_status(user_id: str) -> bool:
    """Kullanıcının abonelik durumunu kontrol eder"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user_id).get()
        
        if not user_doc.exists:
            return False
        
        user_data = user_doc.to_dict()
        subscription_end = user_data.get('subscription_end')
        
        if not subscription_end:
            return False
        
        return subscription_end > datetime.utcnow()
    except Exception as e:
        logger.error(f"Error checking subscription status: {e}")
        return False

def require_active_subscription(user: dict = Depends(get_current_user)):
    """Aktif abonelik gerektirir"""
    if not check_subscription_status(user['user_id']):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required. Please renew your subscription to continue using the bot."
        )
    return user

# Firebase Initialization
async def initialize_firebase():
    """Firebase'i başlatır"""
    try:
        if firebase_admin._apps:
            logger.info("Firebase already initialized")
            return
            
        # Try to load credentials from path first
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            logger.info("Using Firebase credentials from file")
        else:
            # Fallback to environment variable
            cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                try:
                    cred_dict = json.loads(cred_json)
                    cred = credentials.Certificate(cred_dict)
                    logger.info("Using Firebase credentials from environment variable")
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid Firebase credentials JSON: {e}")
            else:
                raise ValueError("Firebase credentials not found. Set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON")
        
        firebase_admin.initialize_app(cred)
        
        # Test the connection
        db = firestore.client()
        test_doc = db.collection('_health').document('test')
        test_doc.set({'timestamp': datetime.utcnow(), 'status': 'healthy'})
        
        logger.info("✅ Firebase initialized successfully")
    except Exception as e:
        logger.critical(f"❌ Firebase initialization failed: {e}")
        raise

# Authentication Endpoints
@app.post("/api/auth/register")
async def register_user(user_data: UserRegistration):
    """Kullanıcı kaydı"""
    try:
        db = firestore.client()
        
        # Email kontrolü
        existing_users = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if existing_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Şifre hash'leme
        password_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt())
        
        # Kullanıcı oluşturma
        trial_days = int(os.getenv('TRIAL_DAYS', 7))
        user_doc = {
            'email': user_data.email,
            'full_name': user_data.full_name,
            'password_hash': password_hash.decode(),
            'created_at': datetime.utcnow(),
            'subscription_start': datetime.utcnow(),
            'subscription_end': datetime.utcnow() + timedelta(days=trial_days),
            'is_trial': True,
            'api_keys_set': False,
            'bot_active': False,
            'last_login': datetime.utcnow()
        }
        
        user_ref = db.collection('users').add(user_doc)
        user_id = user_ref[1].id
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        logger.info(f"New user registered: {user_data.email}")
        
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "trial_days_left": trial_days,
                "is_trial": True,
                "api_keys_set": False
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed for {user_data.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )

@app.post("/api/auth/login")
async def login_user(user_data: UserLogin):
    """Kullanıcı girişi"""
    try:
        db = firestore.client()
        
        # Kullanıcı bulma
        users = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user_doc = users[0]
        user_dict = user_doc.to_dict()
        user_id = user_doc.id
        
        # Şifre kontrolü
        if not bcrypt.checkpw(user_data.password.encode(), user_dict['password_hash'].encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Last login güncelle
        db.collection('users').document(user_id).update({
            'last_login': datetime.utcnow()
        from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore
import bcrypt
import jwt
from cryptography.fernet import Fernet
import os
from contextlib import asynccontextmanager

# Pydantic Models
class UserRegistration(BaseModel):
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: str
    password: str

class TradingSettings(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z]{3,10}USDT$')
    timeframe: str = Field(..., regex=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)$')
    leverage: int = Field(default=5, ge=1, le=125)
    order_size_usdt: float = Field(default=35.0, ge=10.0, le=10000.0)
    stop_loss_percent: float = Field(..., ge=0.1, le=50.0)
    take_profit_percent: float = Field(..., ge=0.1, le=100.0)
    margin_type: str = Field(default="isolated", regex=r'^(isolated|cross)$')
    
    @validator('take_profit_percent')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss_percent' in values and v <= values['stop_loss_percent']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

class APIKeys(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)

class BotAction(BaseModel):
    action: str = Field(..., regex=r'^(start|stop)$')

# Global Variables
app = FastAPI(title="EzyagoTrading Bot", version="2.0.0")
security = HTTPBearer()
connected_websockets: Dict[str, WebSocket] = {}
bot_instances: Dict[str, 'TradingBot'] = {}

# Encryption setup
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# JWT Settings
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_firebase()
    await initialize_bot_manager()
    yield
    # Shutdown
    await cleanup_bots()

app = FastAPI(title="EzyagoTrading Bot", version="2.0.0", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da spesifik domain'ler ekleyin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility Functions
def encrypt_data(data: str) -> str:
    """Veriyi şifreler"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Şifrelenmiş veriyi çözer"""
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except:
        return ""

def create_jwt_token(user_id: str, email: str) -> str:
    """JWT token oluşturur"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[Dict]:
    """JWT token doğrular"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mevcut kullanıcıyı döndürür"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return payload

def check_subscription_status(user_id: str) -> bool:
    """Kullanıcının abonelik durumunu kontrol eder"""
    db = firestore.client()
    user_doc = db.collection('users').document(user_id).get()
    
    if not user_doc.exists:
        return False
    
    user_data = user_doc.to_dict()
    subscription_end = user_data.get('subscription_end')
    
    if not subscription_end:
        return False
    
    return subscription_end > datetime.utcnow()

def require_active_subscription(user: dict = Depends(get_current_user)):
    """Aktif abonelik gerektirir"""
    if not check_subscription_status(user['user_id']):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required"
        )
    return user

# Firebase Initialization
async def initialize_firebase():
    """Firebase'i başlatır"""
    try:
        # Firebase credentials from environment
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            # Fallback to environment variable
            cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
            else:
                raise ValueError("Firebase credentials not found")
        
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        raise

# Authentication Endpoints
@app.post("/api/auth/register")
async def register_user(user_data: UserRegistration):
    """Kullanıcı kaydı"""
    try:
        db = firestore.client()
        
        # Email kontrolü
        existing_user = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Şifre hash'leme
        password_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt())
        
        # Kullanıcı oluşturma
        user_doc = {
            'email': user_data.email,
            'full_name': user_data.full_name,
            'password_hash': password_hash.decode(),
            'created_at': datetime.utcnow(),
            'subscription_start': datetime.utcnow(),
            'subscription_end': datetime.utcnow() + timedelta(days=7),  # 7 gün deneme
            'is_trial': True,
            'api_keys_set': False,
            'bot_active': False
        }
        
        user_ref = db.collection('users').add(user_doc)
        user_id = user_ref[1].id
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "trial_days_left": 7
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/api/auth/login")
async def login_user(user_data: UserLogin):
    """Kullanıcı girişi"""
    try:
        db = firestore.client()
        
        # Kullanıcı bulma
        users = db.collection('users').where('email', '==', user_data.email).limit(1).get()
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user_doc = users[0]
        user_dict = user_doc.to_dict()
        user_id = user_doc.id
        
        # Şifre kontrolü
        if not bcrypt.checkpw(user_data.password.encode(), user_dict['password_hash'].encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        if user_dict.get('is_trial', False):
            subscription_end = user_dict.get('subscription_end')
            if subscription_end:
                remaining = subscription_end - datetime.utcnow()
                trial_days_left = max(0, remaining.days)
        
        # JWT token oluştur
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user_id,
                "email": user_dict['email'],
                "full_name": user_dict['full_name'],
                "api_keys_set": user_dict.get('api_keys_set', False),
                "bot_active": user_dict.get('bot_active', False),
                "is_trial": user_dict.get('is_trial', False),
                "trial_days_left": trial_days_left
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

# API Key Management
@app.post("/api/user/api-keys")
async def save_api_keys(api_keys: APIKeys, user: dict = Depends(get_current_user)):
    """API anahtarlarını kaydeder"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        
        # API anahtarlarını şifrele
        encrypted_api_key = encrypt_data(api_keys.api_key)
        encrypted_api_secret = encrypt_data(api_keys.api_secret)
        
        # Veritabanına kaydet
        user_ref.update({
            'api_key': encrypted_api_key,
            'api_secret': encrypted_api_secret,
            'api_keys_set': True,
            'updated_at': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "API keys saved securely"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save API keys: {str(e)}"
        )

@app.get("/api/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Kullanıcı profil bilgileri"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # Abonelik durumu hesaplama
        trial_days_left = 0
        subscription_active = False
        
        if user_data.get('subscription_end'):
            remaining = user_data['subscription_end'] - datetime.utcnow()
            if remaining.total_seconds() > 0:
                subscription_active = True
                if user_data.get('is_trial', False):
                    trial_days_left = remaining.days
        
        return {
            "id": user['user_id'],
            "email": user_data['email'],
            "full_name": user_data['full_name'],
            "api_keys_set": user_data.get('api_keys_set', False),
            "bot_active": user_data.get('bot_active', False),
            "is_trial": user_data.get('is_trial', False),
            "trial_days_left": trial_days_left,
            "subscription_active": subscription_active,
            "created_at": user_data['created_at'].isoformat() if user_data.get('created_at') else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )

# WebSocket for real-time updates
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket bağlantısı"""
    await websocket.accept()
    connected_websockets[user_id] = websocket
    
    try:
        while True:
            # Heartbeat için ping-pong
            await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }))
    except WebSocketDisconnect:
        if user_id in connected_websockets:
            del connected_websockets[user_id]

async def send_websocket_message(user_id: str, message: dict):
    """WebSocket üzerinden mesaj gönderir"""
    if user_id in connected_websockets:
        try:
            await connected_websockets[user_id].send_text(json.dumps(message))
        except:
            # Bağlantı kopmuşsa listeden çıkar
            if user_id in connected_websockets:
                del connected_websockets[user_id]

# Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Ana sayfa"""
    return FileResponse("static/index.html")

# Health Check
@app.get("/api/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(connected_websockets),
        "active_bots": len(bot_instances)
    }

# Bot Management Endpoints
@app.post("/api/bot/start")
async def start_bot(settings: TradingSettings, user: dict = Depends(require_active_subscription)):
    """Botu başlatır"""
    try:
        db = firestore.client()
        user_doc = db.collection('users').document(user['user_id']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # API anahtarlarını kontrol et
        if not user_data.get('api_keys_set', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please set your API keys first"
            )
        
        # API anahtarlarını çöz
        api_key = decrypt_data(user_data.get('api_key', ''))
        api_secret = decrypt_data(user_data.get('api_secret', ''))
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API keys"
            )
        
        # Trading settings oluştur
        from trading_bot import TradingSettings as BotTradingSettings, bot_manager
        
        bot_settings = BotTradingSettings(
            symbol=settings.symbol,
            timeframe=settings.timeframe,
            leverage=settings.leverage,
            order_size_usdt=settings.order_size_usdt,
            stop_loss_percent=settings.stop_loss_percent,
            take_profit_percent=settings.take_profit_percent,
            margin_type=settings.margin_type,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Botu başlat
        result = await bot_manager.start_bot(
            user['user_id'], 
            bot_settings, 
            send_websocket_message
        )
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db.collection('users').document(user['user_id']).update({
                'bot_active': True,
                'bot_started_at': datetime.utcnow(),
                'current_symbol': settings.symbol
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start bot: {str(e)}"
        )

@app.post("/api/bot/stop")
async def stop_bot(user: dict = Depends(get_current_user)):
    """Botu durdurur"""
    try:
        from trading_bot import bot_manager
        
        result = await bot_manager.stop_bot(user['user_id'])
        
        if result["success"]:
            # Veritabanında bot durumunu güncelle
            db = firestore.client()
            db.collection('users').document(user['user_id']).update({
                'bot_active': False,
                'bot_stopped_at': datetime.utcnow()
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop bot: {str(e)}"
        )

@app.get("/api/bot/status")
async def get_bot_status(user: dict = Depends(get_current_user)):
    """Bot durumunu döndürür"""
    try:
        from trading_bot import bot_manager
        
        status = bot_manager.get_bot_status(user['user_id'])
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bot status: {str(e)}"
        )

@app.get("/api/market/symbols")
async def get_futures_symbols():
    """Futures sembollerini döndürür"""
    try:
        # Binance'den popüler USDT futures sembollerini al
        popular_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "SOLUSDT", "DOTUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT",
            "LINKUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "FILUSDT",
            "TRXUSDT", "XLMUSDT", "VETUSDT", "ICPUSDT", "THETAUSDT"
        ]
        
        return {
            "success": True,
            "symbols": popular_symbols
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get symbols: {str(e)}"
        )

@app.get("/api/market/price/{symbol}")
async def get_symbol_price(symbol: str):
    """Sembol fiyatını döndürür"""
    try:
        # Bu endpoint gerçek zamanlı fiyat için Binance API'si kullanabilir
        # Şimdilik basit bir response döndürüyoruz
        return {
            "success": True,
            "symbol": symbol,
            "price": "0.00",
            "change_24h": "0.00",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get price: {str(e)}"
        )

# Trading History
@app.get("/api/trading/history")
async def get_trading_history(user: dict = Depends(get_current_user)):
    """Kullanıcının trading geçmişini döndürür"""
    try:
        db = firestore.client()
        
        # Son 30 günün işlemlerini al
        trades = db.collection('trades')\
                  .where('user_id', '==', user['user_id'])\
                  .order_by('created_at', direction=firestore.Query.DESCENDING)\
                  .limit(100)\
                  .get()
        
        trade_list = []
        for trade in trades:
            trade_data = trade.to_dict()
            trade_data['id'] = trade.id
            trade_list.append(trade_data)
        
        return {
            "success": True,
            "trades": trade_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trading history: {str(e)}"
        )

# Subscription Management
@app.post("/api/subscription/extend")
async def extend_subscription(days: int, user: dict = Depends(get_current_user)):
    """Aboneliği uzatır (admin veya ödeme sonrası)"""
    try:
        db = firestore.client()
        user_ref = db.collection('users').document(user['user_id'])
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        current_end = user_data.get('subscription_end', datetime.utcnow())
        
        # Eğer abonelik bitmiş ise bugünden başlat, değilse mevcut bitiş tarihine ekle
        if current_end < datetime.utcnow():
            new_end = datetime.utcnow() + timedelta(days=days)
        else:
            new_end = current_end + timedelta(days=days)
        
        user_ref.update({
            'subscription_end': new_end,
            'is_trial': False,
            'last_payment': datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Subscription extended by {days} days",
            "new_end_date": new_end.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend subscription: {str(e)}"
        )

# Bot Management Functions
async def initialize_bot_manager():
    """Bot yöneticisini başlatır"""
    from trading_bot import bot_manager
    print("✅ Bot manager initialized")

async def cleanup_bots():
    """Tüm botları güvenli şekilde kapatır"""
    from trading_bot import bot_manager
    await bot_manager.stop_all_bots()
    print("✅ All bots stopped safely")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
