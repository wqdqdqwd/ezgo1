import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """
    Environment variables ile konfigürasyon
    """
    
    # --- Firebase Admin SDK Ayarları ---
    FIREBASE_CREDENTIALS_JSON: str = os.getenv("FIREBASE_CREDENTIALS_JSON")
    FIREBASE_DATABASE_URL: str = os.getenv("FIREBASE_DATABASE_URL")
    
    # --- Firebase Web App Ayarları (Frontend için) ---
    FIREBASE_WEB_API_KEY: str = os.getenv("FIREBASE_WEB_API_KEY")
    FIREBASE_WEB_AUTH_DOMAIN: str = os.getenv("FIREBASE_WEB_AUTH_DOMAIN")
    FIREBASE_WEB_PROJECT_ID: str = os.getenv("FIREBASE_WEB_PROJECT_ID")
    FIREBASE_WEB_STORAGE_BUCKET: str = os.getenv("FIREBASE_WEB_STORAGE_BUCKET")
    FIREBASE_WEB_MESSAGING_SENDER_ID: str = os.getenv("FIREBASE_WEB_MESSAGING_SENDER_ID")
    FIREBASE_WEB_APP_ID: str = os.getenv("FIREBASE_WEB_APP_ID")

    # --- Güvenlik Ayarları ---
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@ezyago.com")
    
    # --- Ödeme Ayarları ---
    PAYMENT_TRC20_ADDRESS: str = os.getenv("PAYMENT_TRC20_ADDRESS", "TMjSDNto6hoHUV9udDcXVAtuxxX6cnhhv3")
    BOT_PRICE_USD: str = os.getenv("BOT_PRICE_USD", "$15/Ay")

    # --- Redis Ayarları ---
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # --- Rate Limiting Ayarları ---
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    
    # --- Monitoring Ayarları ---
    METRICS_ENABLED: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # --- Uygulama Ayarları ---
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "PRODUCTION")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # --- Binance Ayarları ---
    BASE_URL: str = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com")
    WEBSOCKET_URL: str = os.getenv("BINANCE_WS_URL", "wss://fstream.binance.com")
    
    # --- Bot Varsayılan Ayarları ---
    LEVERAGE: int = int(os.getenv("DEFAULT_LEVERAGE", "10"))
    ORDER_SIZE_USDT: float = float(os.getenv("DEFAULT_ORDER_SIZE_USDT", "100.0"))
    TIMEFRAME: str = os.getenv("DEFAULT_TIMEFRAME", "15m")
    STOP_LOSS_PERCENT: float = float(os.getenv("DEFAULT_STOP_LOSS_PERCENT", "2.0"))
    TAKE_PROFIT_PERCENT: float = float(os.getenv("DEFAULT_TAKE_PROFIT_PERCENT", "3.0"))
    
    # --- Server Ayarları ---
    SERVER_IPS: str = os.getenv("SERVER_IPS", "0.0.0.0")
    
    @classmethod
    def validate_settings(cls):
        """Kritik ayarları kontrol eder"""
        errors = []
        
        if not cls.FIREBASE_CREDENTIALS_JSON:
            errors.append("FIREBASE_CREDENTIALS_JSON eksik")
            
        if not cls.FIREBASE_DATABASE_URL:
            errors.append("FIREBASE_DATABASE_URL eksik")
            
        if not cls.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY eksik - API anahtarları şifrelenemez")
            
        if not cls.FIREBASE_WEB_API_KEY:
            errors.append("FIREBASE_WEB_API_KEY eksik - Frontend çalışmaz")
            
        if errors:
            print("❌ KRİTİK AYARLAR EKSİK:")
            for error in errors:
                print(f"  - {error}")
            print("\n.env dosyanızı kontrol edin!")
            return False
            
        print("✅ Tüm kritik ayarlar mevcut")
        return True

# Global settings instance
settings = Settings()

# Başlangıçta ayarları doğrula
if __name__ == "__main__":
    settings.validate_settings()
