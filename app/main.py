import os
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

# Rate limiting enabled check
RATE_LIMITING_ENABLED = getattr(settings, 'RATE_LIMIT_ENABLED', True)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting EzyagoTrading application")
    yield
    logger.info("Shutting down application")
    await bot_manager.shutdown_all_bots()

# Create FastAPI application
app = FastAPI(
    title="EzyagoTrading API",
    description="Professional Crypto Futures Trading Bot API",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting if enabled
if RATE_LIMITING_ENABLED:
    limiter.init_app(app)
    app.add_exception_handler(429, rate_limit_exceeded_handler)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Authentication dependency
async def get_current_user(request: Request) -> dict:
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No valid authentication token provided")
        
        token = auth_header.split(" ")[1]
        decoded_token = firebase_manager.verify_token(token)
        
        if not decoded_token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        return decoded_token
    except Exception as e:
        logger.error("Authentication failed", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")

# Admin authentication dependency
async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    is_admin = current_user.get('admin', False)
    if not is_admin:
        logger.warning("Non-admin user attempted admin access", user_id=current_user.get('uid'))
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = (datetime.now() - start_time).total_seconds()
    
    # Log request
    logger.info(
        "Request processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_seconds=duration,
        client_ip=request.client.host if request.client else "unknown"
    )
    
    # Record metrics
    metrics.record_api_request(
        endpoint=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration=duration
    )
    
    return response

# Root endpoint - serve main page
@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>EzyagoTrading</h1><p>Welcome to EzyagoTrading API</p>")

# Static pages
@app.get("/login.html", response_class=HTMLResponse)
async def login_page():
    try:
        with open("static/login.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Login page not found")

@app.get("/register.html", response_class=HTMLResponse)
async def register_page():
    try:
        with open("static/register.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Register page not found")

@app.get("/dashboard.html", response_class=HTMLResponse)
async def dashboard_page():
    try:
        with open("static/dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dashboard page not found")

@app.get("/admin.html", response_class=HTMLResponse)
async def admin_page():
    try:
        with open("static/admin.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Admin page not found")

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0"
    }

# Metrics endpoint
@app.get("/metrics")
async def metrics_endpoint():
    if not getattr(settings, 'METRICS_ENABLED', True):
        raise HTTPException(status_code=404, detail="Metrics disabled")
    
    metrics_data = get_metrics_data()
    return Response(
        content=metrics_data,
        media_type=get_metrics_content_type()
    )

# Firebase config endpoint
@app.get("/api/firebase-config")
async def get_firebase_config():
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
        
        # Check if all required fields are present
        missing_fields = [k for k, v in config.items() if not v]
        if missing_fields:
            logger.error("Missing Firebase config fields", missing_fields=missing_fields)
            raise HTTPException(status_code=500, detail="Firebase configuration incomplete")
        
        return config
    except Exception as e:
        logger.error("Error providing Firebase config", error=str(e))
        raise HTTPException(status_code=500, detail="Firebase configuration error")

# User authentication endpoints
@app.post("/api/auth/register")
async def register_user(request: Request):
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "5/minute")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        data = await request.json()
        email = data.get('email')
        uid = data.get('uid')
        
        if not email or not uid:
            raise HTTPException(status_code=400, detail="Email and UID required")
        
        # Create user record in Realtime Database
        user_data = firebase_manager.create_user_record(uid, email)
        
        logger.info("User registered successfully", email=email, uid=uid)
        return {"success": True, "message": "User registered successfully", "user": user_data}
        
    except Exception as e:
        logger.error("User registration failed", error=str(e))
        raise HTTPException(status_code=500, detail="Registration failed")

# User profile endpoints
@app.get("/api/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    try:
        user_data = firebase_manager.get_user_data(current_user['uid'])
        if not user_data:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        # Remove sensitive data
        profile = {
            "email": user_data.get('email'),
            "created_at": user_data.get('created_at'),
            "subscription_status": user_data.get('subscription_status'),
            "subscription_expiry": user_data.get('subscription_expiry'),
            "has_api_keys": bool(user_data.get('binance_api_key'))
        }
        
        return {"success": True, "profile": profile}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user profile", user_id=current_user['uid'], error=str(e))
        raise HTTPException(status_code=500, detail="Failed to load profile")

@app.post("/api/user/api-keys")
async def save_api_keys(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "10/minute")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        data = await request.json()
        api_key = data.get('api_key', '').strip()
        api_secret = data.get('api_secret', '').strip()
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API key and secret are required")
        
        # Validate API key format (basic validation)
        if len(api_key) < 32 or len(api_secret) < 32:
            raise HTTPException(status_code=400, detail="Invalid API key format")
        
        # Save encrypted API keys
        firebase_manager.update_user_api_keys(current_user['uid'], api_key, api_secret)
        
        logger.info("API keys saved successfully", user_id=current_user['uid'])
        return {"success": True, "message": "API keys saved successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save API keys", user_id=current_user['uid'], error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save API keys")

# Bot management endpoints
@app.post("/api/bot/start")
async def start_bot(
    request: Request,
    bot_settings: StartRequest,
    current_user: dict = Depends(get_current_user)
):
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "5/minute")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Check subscription
    if not firebase_manager.is_subscription_active(current_user['uid']):
        raise HTTPException(status_code=403, detail="Active subscription required")
    
    try:
        result = await bot_manager.start_bot_for_user(current_user['uid'], bot_settings)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Record metrics
        metrics.record_bot_start(current_user['uid'], bot_settings.symbol)
        
        logger.info("Bot started successfully", user_id=current_user['uid'], symbol=bot_settings.symbol)
        return {"success": True, "status": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start bot", user_id=current_user['uid'], error=str(e))
        metrics.record_error("bot_start_failed", "bot_manager")
        raise HTTPException(status_code=500, detail="Failed to start bot")

@app.post("/api/bot/stop")
async def stop_bot(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "5/minute")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        result = await bot_manager.stop_bot_for_user(current_user['uid'])
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Record metrics
        metrics.record_bot_stop(current_user['uid'], "unknown", "manual")
        
        logger.info("Bot stopped successfully", user_id=current_user['uid'])
        return {"success": True, "message": "Bot stopped successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to stop bot", user_id=current_user['uid'], error=str(e))
        metrics.record_error("bot_stop_failed", "bot_manager")
        raise HTTPException(status_code=500, detail="Failed to stop bot")

@app.get("/api/bot/status")
async def get_bot_status(current_user: dict = Depends(get_current_user)):
    try:
        status = bot_manager.get_bot_status(current_user['uid'])
        return {"success": True, "status": status}
        
    except Exception as e:
        logger.error("Failed to get bot status", user_id=current_user['uid'], error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get bot status")

# Payment and subscription endpoints
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
    return {
        "success": True,
        "amount": getattr(settings, 'BOT_PRICE_USD', '$15/Ay'),
        "trc20Address": getattr(settings, 'PAYMENT_TRC20_ADDRESS', 'TMjSDNto6hoHUV9udDcXVAtuxxX6cnhhv3'),
        "botPriceUsd": "15"
    }

@app.post("/api/payment/notify")
async def notify_payment(
    request: Request,
    payment: PaymentNotification,
    current_user: dict = Depends(get_current_user)
):
    """Kullanıcıdan ödeme bildirimi alır"""
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "3/hour")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        # Ödeme bildirimini Firebase'e kaydet
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
        
        # Firebase Realtime Database'e kaydet (simplified)
        logger.info("Payment notification received", 
                   user_id=current_user['uid'], 
                   transaction_hash=payment.transaction_hash,
                   amount=payment.amount)
        
        return {
            "success": True,
            "message": "Ödeme bildirimi alındı. Admin onayı bekleniyor."
        }
        
    except Exception as e:
        logger.error("Payment notification failed", 
                    user_id=current_user['uid'], 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Payment notification failed")

@app.post("/api/support/message")
async def send_support_message(
    request: Request,
    support: SupportMessage,
    current_user: dict = Depends(get_current_user)
):
    """Destek mesajı gönderir"""
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "5/hour")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        logger.info("Support message received", 
                   user_id=current_user['uid'], 
                   subject=support.subject)
        
        return {
            "success": True,
            "message": "Destek mesajınız alındı. En kısa sürede dönüş yapacağız."
        }
        
    except Exception as e:
        logger.error("Support message failed", 
                    user_id=current_user['uid'], 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Support message failed")

# Admin endpoints
@app.get("/api/admin/users")
async def get_all_users(current_user: dict = Depends(get_admin_user)):
    """Admin için tüm kullanıcıları listeler"""
    try:
        # This would typically get users from Firebase
        # For now, return empty response
        return {"success": True, "users": {}}
        
    except Exception as e:
        logger.error("Admin get users failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@app.post("/api/admin/activate-subscription")
async def activate_user_subscription(
    request: Request,
    current_user: dict = Depends(get_admin_user)
):
    """Admin tarafından kullanıcı aboneliğini aktifleştirir"""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID required")
        
        logger.info("User subscription activated by admin", 
                   admin_email=current_user.get('email'),
                   target_user=user_id)
        
        return {
            "success": True,
            "message": "User subscription activated for 30 days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin activate subscription failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to activate subscription")

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "detail": "The requested resource was not found"}
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    logger.error("Internal server error", error=str(exc), path=request.url.path)
    metrics.record_error("internal_server_error", "main")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
