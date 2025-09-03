import os
from dotenv import load_dotenv

# Proje ana dizinindeki .env dosyasını yükler
# Bu, os.getenv() çağrılarının .env dosyasındaki değerleri bulmasını sağlar.
load_dotenv()

class Settings:
    """
    Uygulama ayarlarını ortam değişkenlerinden (environment variables) yükleyen sınıf.
    """
    # --- Firebase Admin SDK Ayarları (Backend için gizli kalmalı) ---
    # Bu değişkenler, Firebase hizmet hesabı JSON dosyasının içeriği olmalıdır.
    # Örnek: FIREBASE_CREDENTIALS_JSON='{"type": "service_account", ...}'
    FIREBASE_CREDENTIALS_JSON: str = os.getenv("FIREBASE_CREDENTIALS_JSON")
    FIREBASE_DATABASE_URL: str = os.getenv("FIREBASE_DATABASE_URL")

    # --- Güvenlik Ayarları (Gizli Kalmalı) ---
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    # ADMIN_EMAIL, kullanıcı oluşturulurken Realtime Database'deki rol için bir işaretçidir.
    # Asıl admin yetkilendirmesi Custom Claims ile yapılır.
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com") 
    
    # --- Ödeme Ayarları ---
    PAYMENT_TRC20_ADDRESS: str = os.getenv("PAYMENT_TRC20_ADDRESS")

    # --- Bot için Varsayılan Ayarlar ---
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "LIVE") # Varsayılan olarak LIVE
    BASE_URL: str = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com")
    WEBSOCKET_URL: str = os.getenv("BINANCE_WS_URL", "wss://fstream.binance.com")
    LEVERAGE: int = int(os.getenv("DEFAULT_LEVERAGE", "10"))
    ORDER_SIZE_USDT: float = float(os.getenv("DEFAULT_ORDER_SIZE_USDT", "100.0"))
    TIMEFRAME: str = os.getenv("DEFAULT_TIMEFRAME", "15m")
    STOP_LOSS_PERCENT: float = float(os.getenv("DEFAULT_STOP_LOSS_PERCENT", "0.04"))
    
    # --- Firebase Web App Yapılandırması (Frontend için Güvenli) ---
    # Bu anahtarların istemci tarafında görünmesi güvenlidir.
    # .env dosyanıza bu değişkenleri eklemelisiniz ve Firebase Projenizden almalısınız.
    FIREBASE_WEB_API_KEY: str = os.getenv("FIREBASE_WEB_API_KEY")
    FIREBASE_WEB_AUTH_DOMAIN: str = os.getenv("FIREBASE_WEB_AUTH_DOMAIN")
    FIREBASE_WEB_PROJECT_ID: str = os.getenv("FIREBASE_WEB_PROJECT_ID")
    FIREBASE_WEB_STORAGE_BUCKET: str = os.getenv("FIREBASE_WEB_STORAGE_BUCKET")
    FIREBASE_WEB_MESSAGING_SENDER_ID: str = os.getenv("FIREBASE_WEB_MESSAGING_SENDER_ID")
    FIREBASE_WEB_APP_ID: str = os.getenv("FIREBASE_WEB_APP_ID")
    # FIREBASE_WEB_MEASUREMENT_ID: str = os.getenv("FIREBASE_WEB_MEASUREMENT_ID") # Eğer kullanılıyorsa ekleyebilirsiniz


# Ayarları projenin her yerinden erişilebilir hale getirmek için bir nesne oluşturulur.
settings = Settings()
