# config.py

import os
from dotenv import load_dotenv

# Proje ana dizinindeki .env dosyasını yükler
load_dotenv()

class Settings:
    """
    Uygulama ayarlarını ortam değişkenlerinden (environment variables) yükleyen sınıf.
    """
    # --- Firebase Admin SDK Ayarları (Backend için gizli kalmalı) ---
    FIREBASE_CREDENTIALS_JSON: str = os.getenv("FIREBASE_CREDENTIALS_JSON")
    FIREBASE_DATABASE_URL: str = os.getenv("FIREBASE_DATABASE_URL")

    # --- Güvenlik Ayarları (Gizli Kalmalı) ---
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com") 
    
    # --- Ödeme Ayarları ---
    PAYMENT_TRC20_ADDRESS: str = os.getenv("PAYMENT_TRC20_ADDRESS")

    # --- Bot için Varsayılan Ayarlar ---
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "LIVE")
    BASE_URL: str = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com")
    WEBSOCKET_URL: str = os.getenv("BINANCE_WS_URL", "wss://fstream.binance.com")
    
    # Yeni Kaldıraç ayarı: .env'den alınacak, yoksa varsayılan 10x
    LEVERAGE: int = int(os.getenv("DEFAULT_LEVERAGE", "10"))

    # İşlem büyüklüğü: .env'den alınacak, yoksa varsayılan 100 USDT
    ORDER_SIZE_USDT: float = float(os.getenv("DEFAULT_ORDER_SIZE_USDT", "100.0"))

    # Zaman dilimi: .env'den alınacak, yoksa varsayılan 15m
    TIMEFRAME: str = os.getenv("DEFAULT_TIMEFRAME", "15m")
    
    # STOP_LOSS_PERCENT ayarı artık kullanılmayacak.
    
    # --- Zaman Dilimine Göre PnL Ayarları ---
    # Bu değerler, kaldıraçlı işlemde elde etmek istediğiniz gerçek PnL yüzdesini temsil eder.
    # Örneğin, 5m için %3 kar hedefi, 10x kaldıraç ile %0.3'lük bir fiyat değişimine denk gelir.
    TIMEFRAME_SETTINGS = {
        "5m": {
            "TP_PNL": 3.0,  # %3 Gerçek Kar Al (Kaldıraçlı PnL)
            "SL_PNL": 2.0   # %2 Gerçek Zarar Durdur (Kaldıraçlı PnL)
        },
        "15m": {
            "TP_PNL": 10.0, # %10 Gerçek Kar Al
            "SL_PNL": 3.0   # %3 Gerçek Zarar Durdur
        },
    }

    # --- Firebase Web App Yapılandırması (Frontend için Güvenli) ---
    FIREBASE_WEB_API_KEY: str = os.getenv("FIREBASE_WEB_API_KEY")
    FIREBASE_WEB_AUTH_DOMAIN: str = os.getenv("FIREBASE_WEB_AUTH_DOMAIN")
    FIREBASE_WEB_PROJECT_ID: str = os.getenv("FIREBASE_WEB_PROJECT_ID")
    FIREBASE_WEB_STORAGE_BUCKET: str = os.getenv("FIREBASE_WEB_STORAGE_BUCKET")
    FIREBASE_WEB_MESSAGING_SENDER_ID: str = os.getenv("FIREBASE_WEB_MESSAGING_SENDER_ID")
    FIREBASE_WEB_APP_ID: str = os.getenv("FIREBASE_WEB_APP_ID")

settings = Settings()
