from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from app.config import settings
from app.bot_manager import bot_manager
from app.utils.logger import get_logger

logger = get_logger("main")

# FastAPI uygulama başlatma
app = FastAPI()

# CORS middleware ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da specific domains kullanın
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routes
from app.routes.static import router as static_router
from app.routes.auth import router as auth_router

# Include routers
app.include_router(static_router)
app.include_router(auth_router)

@app.on_event("startup")
async def startup_event():
    """Uygulama başlatma"""
    logger.info("EzyagoTrading starting up...")
    # Firebase manager otomatik olarak başlatılacak

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }

# Firebase config endpoint for frontend
@app.get("/api/firebase-config")
async def get_firebase_config():
    """Frontend için Firebase konfigürasyonu"""
    try:
        firebase_web_config = {
            "apiKey": settings.FIREBASE_WEB_API_KEY,
            "authDomain": settings.FIREBASE_WEB_AUTH_DOMAIN,
            "databaseURL": settings.FIREBASE_DATABASE_URL,
            "projectId": settings.FIREBASE_WEB_PROJECT_ID,
            "storageBucket": settings.FIREBASE_WEB_STORAGE_BUCKET,
            "messagingSenderId": settings.FIREBASE_WEB_MESSAGING_SENDER_ID,
            "appId": settings.FIREBASE_WEB_APP_ID
        }
        
        # Eksik alanları kontrol et
        missing_fields = [k for k, v in firebase_web_config.items() if not v]
        if missing_fields:
            logger.warning(f"Missing Firebase config fields: {missing_fields}")
        
        return firebase_web_config
    except Exception as e:
        logger.error(f"Firebase config error: {e}")
        raise HTTPException(status_code=500, detail="Firebase configuration error")

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    try:
        from app.utils.metrics import get_metrics_data, get_metrics_content_type
        metrics_data = get_metrics_data()
        return JSONResponse(
            content=metrics_data,
            media_type=get_metrics_content_type()
        )
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return {"error": "Metrics not available"}

@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapatma"""
    logger.info("EzyagoTrading shutting down...")
    await bot_manager.shutdown_all_bots()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
