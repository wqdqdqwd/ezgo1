import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class Settings:
    """
    Uygulama ayarlarını ortam değişkenlerinden yükleyen sınıf.
    Çoklu kullanıcı ve çoklu coin desteği için güncellenmiş ayarlar.
    """
    
    # --- Firebase Admin SDK Ayarları ---
    FIREBASE_CREDENTIALS_JSON: str = os.getenv("FIREBASE_CREDENTIALS_JSON")
    FIREBASE_DATABASE_URL: str = os.getenv("FIREBASE_DATABASE_URL")

    # --- Firebase Web App Yapılandırması ---
    FIREBASE_WEB_API_KEY: str = os.getenv("FIREBASE_WEB_API_KEY")
    FIREBASE_WEB_AUTH_DOMAIN: str = os.getenv("FIREBASE_WEB_AUTH_DOMAIN")
    FIREBASE_WEB_PROJECT_ID: str = os.getenv("FIREBASE_WEB_PROJECT_ID")
    FIREBASE_WEB_STORAGE_BUCKET: str = os.getenv("FIREBASE_WEB_STORAGE_BUCKET")
    FIREBASE_WEB_MESSAGING_SENDER_ID: str = os.getenv("FIREBASE_WEB_MESSAGING_SENDER_ID")
    FIREBASE_WEB_APP_ID: str = os.getenv("FIREBASE_WEB_APP_ID")

    # --- Güvenlik Ayarları ---
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@ezyagotrading.com")
    
    # --- Ödeme Ayarları ---
    PAYMENT_TRC20_ADDRESS: str = os.getenv("PAYMENT_TRC20_ADDRESS", "TXYZexampleAddress123456789")
    MONTHLY_SUBSCRIPTION_PRICE: float = float(os.getenv("MONTHLY_SUBSCRIPTION_PRICE", "15.0"))

    # --- Uygulama Ayarları ---
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "LIVE")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # --- Bot Sistem Ayarları ---
    MAX_BOTS_PER_USER: int = int(os.getenv("MAX_BOTS_PER_USER", "4"))
    MAX_TOTAL_SYSTEM_BOTS: int = int(os.getenv("MAX_TOTAL_SYSTEM_BOTS", "1000"))
    
    # --- Binance API Ayarları ---
    # Binance URLs ortam değişkenlerinden alınır
    BINANCE_BASE_URL: str = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com")
    BINANCE_WS_URL: str = os.getenv("BINANCE_WS_URL", "wss://fstream.binance.com")
    
    # Testnet URLs
    BINANCE_TESTNET_BASE_URL: str = os.getenv("BINANCE_TESTNET_BASE_URL", "https://testnet.binancefuture.com")
    BINANCE_TESTNET_WS_URL: str = os.getenv("BINANCE_TESTNET_WS_URL", "wss://stream.binancefuture.com")
    
    # --- Varsayılan Bot Ayarları ---
    DEFAULT_LEVERAGE: int = int(os.getenv("DEFAULT_LEVERAGE", "10"))
    DEFAULT_ORDER_SIZE_USDT: float = float(os.getenv("DEFAULT_ORDER_SIZE_USDT", "20.0"))
    DEFAULT_TIMEFRAME: str = os.getenv("DEFAULT_TIMEFRAME", "15m")
    DEFAULT_STOP_LOSS_PERCENT: float = float(os.getenv("DEFAULT_STOP_LOSS_PERCENT", "2.0"))
    DEFAULT_TAKE_PROFIT_PERCENT: float = float(os.getenv("DEFAULT_TAKE_PROFIT_PERCENT", "4.0"))
    
    # --- Risk Yönetimi Ayarları ---
    MIN_ORDER_SIZE_USDT: float = float(os.getenv("MIN_ORDER_SIZE_USDT", "10.0"))
    MAX_ORDER_SIZE_USDT: float = float(os.getenv("MAX_ORDER_SIZE_USDT", "10000.0"))
    MIN_LEVERAGE: int = int(os.getenv("MIN_LEVERAGE", "1"))
    MAX_LEVERAGE: int = int(os.getenv("MAX_LEVERAGE", "125"))
    MIN_STOP_LOSS_PERCENT: float = float(os.getenv("MIN_STOP_LOSS_PERCENT", "0.5"))
    MAX_STOP_LOSS_PERCENT: float = float(os.getenv("MAX_STOP_LOSS_PERCENT", "25.0"))
    MIN_TAKE_PROFIT_PERCENT: float = float(os.getenv("MIN_TAKE_PROFIT_PERCENT", "0.5"))
    MAX_TAKE_PROFIT_PERCENT: float = float(os.getenv("MAX_TAKE_PROFIT_PERCENT", "50.0"))
    
    # --- Trading Stratejisi Ayarları ---
    # EMA Crossover Strategy
    EMA_SHORT_PERIOD: int = int(os.getenv("EMA_SHORT_PERIOD", "9"))
    EMA_LONG_PERIOD: int = int(os.getenv("EMA_LONG_PERIOD", "21"))
    
    # Desteklenen timeframe'ler
    SUPPORTED_TIMEFRAMES: list = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    
    # --- Rate Limiting Ayarları ---
    API_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "1200"))
    WEBSOCKET_RECONNECT_DELAY: int = int(os.getenv("WEBSOCKET_RECONNECT_DELAY", "5"))
    
    # --- Loglama Ayarları ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "False").lower() == "true"
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "logs/trading_bot.log")
    
    # --- Abonelik Ayarları ---
    TRIAL_PERIOD_DAYS: int = int(os.getenv("TRIAL_PERIOD_DAYS", "7"))
    SUBSCRIPTION_CHECK_INTERVAL: int = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL", "60"))  # saniye
    
    # --- Demo Mode Ayarları ---
    DEMO_MODE_ENABLED: bool = os.getenv("DEMO_MODE_ENABLED", "True").lower() == "true"
    DEMO_BALANCE_USDT: float = float(os.getenv("DEMO_BALANCE_USDT", "1000.0"))
    
    # --- Popüler Coin Listesi ---
    POPULAR_SYMBOLS: list = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT",
        "DOTUSDT", "AVAXUSDT", "MATICUSDT", "LINKUSDT", "UNIUSDT",
        "LTCUSDT", "BCHUSDT", "XLMUSDT", "ATOMUSDT", "FILUSDT"
    ]
    
    # --- Sistem Sınırları ---
    MAX_WEBSOCKET_CONNECTIONS: int = int(os.getenv("MAX_WEBSOCKET_CONNECTIONS", "500"))
    MAX_CONCURRENT_ORDERS_PER_USER: int = int(os.getenv("MAX_CONCURRENT_ORDERS_PER_USER", "10"))
    
    # --- Performans Ayarları ---
    KLINE_HISTORY_LIMIT: int = int(os.getenv("KLINE_HISTORY_LIMIT", "50"))
    POSITION_CHECK_INTERVAL: int = int(os.getenv("POSITION_CHECK_INTERVAL", "30"))  # saniye
    
    # --- Güvenlik Ayarları ---
    SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION_MINUTES: int = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))
    
    # --- Bakım Modu ---
    MAINTENANCE_MODE: bool = os.getenv("MAINTENANCE_MODE", "False").lower() == "true"
    MAINTENANCE_MESSAGE: str = os.getenv("MAINTENANCE_MESSAGE", "Sistem bakımda. Lütfen daha sonra tekrar deneyin.")
    
    # --- Geliştirici Ayarları ---
    ENABLE_DEBUG_LOGS: bool = os.getenv("ENABLE_DEBUG_LOGS", "False").lower() == "true"
    MOCK_BINANCE_API: bool = os.getenv("MOCK_BINANCE_API", "False").lower() == "true"
    
    @classmethod
    def validate_settings(cls):
        """Kritik ayarların varlığını kontrol eder"""
        required_settings = [
            'FIREBASE_CREDENTIALS_JSON',
            'FIREBASE_DATABASE_URL',
            'ENCRYPTION_KEY'
        ]
        
        missing_settings = []
        for setting in required_settings:
            if not getattr(cls, setting):
                missing_settings.append(setting)
        
        if missing_settings:
            raise ValueError(f"Eksik ayarlar: {', '.join(missing_settings)}")
        
        # Değer aralığı kontrolleri
        if cls.MAX_BOTS_PER_USER < 1 or cls.MAX_BOTS_PER_USER > 10:
            raise ValueError("MAX_BOTS_PER_USER 1-10 arasında olmalı")
        
        if cls.DEFAULT_TIMEFRAME not in cls.SUPPORTED_TIMEFRAMES:
            raise ValueError(f"DEFAULT_TIMEFRAME desteklenen timeframe'lerden biri olmalı: {cls.SUPPORTED_TIMEFRAMES}")
        
        print("✅ Tüm ayarlar geçerli")
        return True
    
    @classmethod
    def get_binance_urls(cls, testnet: bool = False):
        """Testnet/Mainnet durumuna göre Binance URL'lerini döndürür"""
        if testnet:
            return {
                'base_url': cls.BINANCE_TESTNET_BASE_URL,
                'ws_url': cls.BINANCE_TESTNET_WS_URL
            }
        else:
            return {
                'base_url': cls.BINANCE_BASE_URL,
                'ws_url': cls.BINANCE_WS_URL
            }
    
    @classmethod
    def get_default_bot_settings(cls):
        """Varsayılan bot ayarlarını döndürür"""
    @classmethod
    def get_default_bot_settings(cls):
        """Varsayılan bot ayarlarını döndürür"""
        return {
            'leverage': cls.DEFAULT_LEVERAGE,
            'order_size': cls.DEFAULT_ORDER_SIZE_USDT,
            'timeframe': cls.DEFAULT_TIMEFRAME,
            'stop_loss': cls.DEFAULT_STOP_LOSS_PERCENT,
            'take_profit': cls.DEFAULT_TAKE_PROFIT_PERCENT
        }
    
    @classmethod
    def get_risk_limits(cls):
        """Risk yönetimi sınırlarını döndürür"""
        return {
            'min_order_size': cls.MIN_ORDER_SIZE_USDT,
            'max_order_size': cls.MAX_ORDER_SIZE_USDT,
            'min_leverage': cls.MIN_LEVERAGE,
            'max_leverage': cls.MAX_LEVERAGE,
            'min_stop_loss': cls.MIN_STOP_LOSS_PERCENT,
            'max_stop_loss': cls.MAX_STOP_LOSS_PERCENT,
            'min_take_profit': cls.MIN_TAKE_PROFIT_PERCENT,
            'max_take_profit': cls.MAX_TAKE_PROFIT_PERCENT
        }
    
    @classmethod
    def get_system_limits(cls):
        """Sistem sınırlarını döndürür"""
        return {
            'max_bots_per_user': cls.MAX_BOTS_PER_USER,
            'max_total_bots': cls.MAX_TOTAL_SYSTEM_BOTS,
            'max_websocket_connections': cls.MAX_WEBSOCKET_CONNECTIONS,
            'supported_timeframes': cls.SUPPORTED_TIMEFRAMES,
            'popular_symbols': cls.POPULAR_SYMBOLS
        }

# Ayarları doğrula
try:
    settings = Settings()
    if not settings.MOCK_BINANCE_API:  # Mock modda değilse ayarları doğrula
        settings.validate_settings()
except Exception as e:
    print(f"⚠️ Ayar doğrulama hatası: {e}")
    print("Lütfen .env dosyanızı kontrol edin")
    # Production'da burada uygulama durdurulabilir
    # raise e

# Global settings instance
settings = Settings()
