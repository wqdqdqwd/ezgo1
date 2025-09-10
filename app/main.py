from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator
from contextlib import asynccontextmanager

# Import custom modules
from app.config import settings
from app.firebase_manager import firebase_manager
from app.bot_manager import bot_manager, StartRequest
from app.utils.logger import get_logger
from app.utils.metrics import metrics, get_metrics_data, get_metrics_content_type
from app.utils.rate_limiter import limiter, rate_limit_exceeded_handler
from app.utils.validation import validate_user_input

logger = get_logger("main")

# Pydantic Models
class UserRegistration(BaseModel):
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: str
    password: str

class ApiKeysRequest(BaseModel):
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)

class BotSettingsRequest(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z]{3,10}USDT$')
    timeframe: str = Field(..., regex=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)$')
    leverage: int = Field(default=10, ge=1, le=125)
    order_size: float = Field(default=35.0, ge=10.0, le=10000.0)
    stop_loss: float = Field(..., ge=0.1, le=50.0)
    take_profit: float = Field(..., ge=0.1, le=100.0)
    
    @validator('take_profit')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss' in values and v <= values['stop_loss']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

# Connected WebSocket clients
connected_websockets: Dict[str, WebSocket] = {}

# Authentication helper
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user from Firebase token"""
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

# Admin user helper
def get_admin_user(current_user: dict = Depends(get_current_user)):
    """Verify user has admin privileges"""
    # Check if user has admin custom claim
    if not current_user.get('admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges"
        )
    return current_user

# App lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting EzyagoTrading application")
    yield
    # Shutdown
    logger.info("Shutting down EzyagoTrading application")
    await bot_manager.shutdown_all_bots()

# Create FastAPI app
app = FastAPI(
    title="EzyagoTrading API",
    description="Professional Crypto Futures Trading Bot API",
    version="2.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
if hasattr(limiter, 'init_app'):
    limiter.init_app(app)
app.add_exception_handler(429, rate_limit_exceeded_handler)

# Request/Response logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = datetime.now()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = (datetime.now() - start_time).total_seconds()
    
    # Log request
    logger.info(
        "HTTP Request",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        duration=duration
    )
    
    # Record metrics
    metrics.record_api_request(
        endpoint=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration=duration
    )
    
    return response

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routes
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve main page"""
    return FileResponse("static/index.html")

@app.get("/login.html", response_class=HTMLResponse)
async def serve_login():
    """Serve login page"""
    return FileResponse("static/login.html")

@app.get("/register.html", response_class=HTMLResponse)
async def serve_register():
    """Serve register page"""
    return FileResponse("static/register.html")

@app.get("/dashboard.html", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve dashboard page"""
    return FileResponse("static/dashboard.html")

@app.get("/admin.html", response_class=HTMLResponse)
async def serve_admin():
    """Serve admin page"""
    return FileResponse("static/admin.html")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "active_connections": len(connected_websockets),
        "active_bots": len(bot_manager.active_bots)
    }

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return JSONResponse(
        content=get_metrics_data(),
        media_type=get_metrics_content_type()
    )

# Firebase config for frontend
@app.get("/api/firebase-config")
async def get_firebase_config():
    """Get Firebase configuration for frontend"""
    return {
        "apiKey": settings.FIREBASE_WEB_API_KEY,
        "authDomain": settings.FIREBASE_WEB_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_WEB_PROJECT_ID,
        "storageBucket": settings.FIREBASE_WEB_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_WEB_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_WEB_APP_ID
    }

# User management
@app.post("/api/user/api-keys")
@limiter.limit("5/minute")
async def save_api_keys(
    request,
    api_keys: ApiKeysRequest,
    current_user: dict = Depends(get_current_user)
):
    """Save user's Binance API keys"""
    try:
        firebase_manager.update_user_api_keys(
            current_user['uid'],
            api_keys.api_key,
            api_keys.api_secret
        )
        
        logger.info("API keys updated", user_id=current_user['uid'])
        
        return {
            "success": True,
            "message": "API keys saved successfully"
        }
    except Exception as e:
        logger.error("Failed to save API keys", user_id=current_user['uid'], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save API keys"
        )

@app.get("/api/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get user profile information"""
    try:
        user_data = firebase_manager.get_user_data(current_user['uid'])
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Remove sensitive data
        safe_data = {
            "email": user_data.get('email'),
            "created_at": user_data.get('created_at'),
            "subscription_status": user_data.get('subscription_status'),
            "subscription_expiry": user_data.get('subscription_expiry'),
            "has_api_keys": bool(user_data.get('binance_api_key'))
        }
        
        return {
            "success": True,
            "user": safe_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user profile", user_id=current_user['uid'], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )

# Bot management
@app.post("/api/bot/start")
@limiter.limit("3/minute")
async def start_bot(
    request,
    bot_settings: BotSettingsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Start trading bot for user"""
    try:
        # Check subscription
        if not firebase_manager.is_subscription_active(current_user['uid']):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Active subscription required"
            )
        
        # Convert to StartRequest format
        start_request = StartRequest(
            symbol=bot_settings.symbol,
            timeframe=bot_settings.timeframe,
            leverage=bot_settings.leverage,
            order_size=bot_settings.order_size,
            stop_loss=bot_settings.stop_loss,
            take_profit=bot_settings.take_profit
        )
        
        # Start bot
        result = await bot_manager.start_bot_for_user(current_user['uid'], start_request)
        
        metrics.record_bot_start(current_user['uid'], bot_settings.symbol)
        
        return {
            "success": True,
            "status": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start bot", user_id=current_user['uid'], error=str(e))
        metrics.record_error("bot_start_failed", "bot_manager")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start bot"
        )

@app.post("/api/bot/stop")
@limiter.limit("10/minute")
async def stop_bot(
    request,
    current_user: dict = Depends(get_current_user)
):
    """Stop trading bot for user"""
    try:
        result = await bot_manager.stop_bot_for_user(current_user['uid'])
        
        metrics.record_bot_stop(current_user['uid'], "unknown", "manual")
        
        return {
            "success": True,
            "message": result.get("message", "Bot stopped")
        }
        
    except Exception as e:
        logger.error("Failed to stop bot", user_id=current_user['uid'], error=str(e))
        metrics.record_error("bot_stop_failed", "bot_manager")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop bot"
        )

@app.get("/api/bot/status")
async def get_bot_status(current_user: dict = Depends(get_current_user)):
    """Get bot status for user"""
    try:
        status_data = bot_manager.get_bot_status(current_user['uid'])
        
        return {
            "success": True,
            "status": status_data
        }
        
    except Exception as e:
        logger.error("Failed to get bot status", user_id=current_user['uid'], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get bot status"
        )

# Admin endpoints
@app.get("/api/admin/users")
async def get_all_users(admin_user: dict = Depends(get_admin_user)):
    """Get all users (admin only)"""
    try:
        # This would need to be implemented in firebase_manager
        # For now, return mock data
        return {
            "success": True,
            "users": {},
            "total": 0
        }
    except Exception as e:
        logger.error("Failed to get users", admin_id=admin_user['uid'], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )

@app.post("/api/admin/activate-subscription")
async def activate_subscription(
    request_data: dict,
    admin_user: dict = Depends(get_admin_user)
):
    """Activate subscription for user (admin only)"""
    try:
        user_id = request_data.get('user_id')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID required"
            )
        
        # This would need to be implemented in firebase_manager
        # For now, return success
        return {
            "success": True,
            "message": "Subscription activated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to activate subscription", admin_id=admin_user['uid'], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate subscription"
        )

# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket connection for real-time updates"""
    await websocket.accept()
    connected_websockets[user_id] = websocket
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for now
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
    except WebSocketDisconnect:
        if user_id in connected_websockets:
            del connected_websockets[user_id]
        logger.info("WebSocket disconnected", user_id=user_id)
    except Exception as e:
        logger.error("WebSocket error", user_id=user_id, error=str(e))
        if user_id in connected_websockets:
            del connected_websockets[user_id]

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler"""
    logger.error("Internal server error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )
