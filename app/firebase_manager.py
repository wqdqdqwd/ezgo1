import firebase_admin
from firebase_admin import credentials, db, auth
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.utils.crypto import encrypt_data, decrypt_data
import json # json modülü import edildi
from app.utils.logger import get_logger
from app.utils.error_handler import robust_firebase_call

logger = get_logger("firebase_manager")

class FirebaseManager:
    def __init__(self):
        try:
            if not firebase_admin._apps: # Firebase uygulamasının zaten başlatılıp başlatılmadığını kontrol et
                if not settings.FIREBASE_CREDENTIALS_JSON or not settings.FIREBASE_DATABASE_URL:
                    raise ValueError("Firebase kimlik bilgileri (JSON veya Database URL) ayarlanmamış.")
                
                # FIREBASE_CREDENTIALS_JSON bir string olduğu için JSON'a ayrıştır
                cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': settings.FIREBASE_DATABASE_URL
                })
            logger.info("Firebase Admin SDK initialized successfully")
        except Exception as e:
            logger.critical("Firebase initialization failed", error=str(e))
            raise e 

    @robust_firebase_call(max_attempts=2)
    async def verify_token(self, token: str):
        """
        Firebase ID Token'ı doğrular ve decoded payload'u döndürür.
        Bu payload kullanıcının UID'si ve custom claims'leri (örn. 'admin': True) içerir.
        """
        try:
            return auth.verify_id_token(token)
        except Exception as e:
            logger.error("Token verification failed", error=str(e))
            # Hata durumunda yetkilendirme katmanında işlenmek üzere None döndür
            return None

    def get_user_ref(self, uid: str):
        """Belirli bir kullanıcı için Realtime Database referansı döndürür."""
        return db.reference(f'users/{uid}')

    def get_trades_ref(self, uid: str):
        """Belirli bir kullanıcının işlem geçmişi için Realtime Database referansı döndürür."""
        return db.reference(f'trades/{uid}')

    def create_user_record(self, uid: str, email: str):
        """
        Yeni bir Firebase kullanıcısı için Realtime Database'de kayıt oluşturur.
        Rol ataması settings.ADMIN_EMAIL'e göre yapılır, ancak admin yetkisi 
        için Firebase Custom Claims'in ayrıca atanması gerektiğini unutmayın.
        """
        user_ref = self.get_user_ref(uid)
        trial_end_date = datetime.now(timezone.utc) + timedelta(days=7)
        
        # Realtime Database'deki 'role' alanı, yalnızca bir veri işaretçisidir.
        # Asıl yetkilendirme get_admin_user fonksiyonunda token'dan gelen custom claims ile yapılır.
        user_role_in_db = 'admin' if email and email.lower() == settings.ADMIN_EMAIL.lower() else 'user'

        user_data = {
            'email': email,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'subscription_status': 'trial',
            'subscription_expiry': trial_end_date.isoformat(),
            'binance_api_key': '', # Başlangıçta boş
            'binance_api_secret': '', # Başlangıçta boş
            'role': user_role_in_db # Sadece Realtime DB'de gösterim için
        }
        user_ref.set(user_data)
        logger.info("New user record created", email=email, uid=uid, role=user_role_in_db)
        return user_data

    @robust_firebase_call(max_attempts=2)
    def get_user_data(self, uid: str) -> dict | None:
        """
        Belirli bir kullanıcının Realtime Database'deki verilerini çeker
        ve API anahtarlarını çözer (decrypt eder).
        """
        user_ref = self.get_user_ref(uid)
        data = user_ref.get()
        if data:
            # API anahtarlarını çekmeden önce çöz
            data['binance_api_key'] = decrypt_data(data.get('binance_api_key', ''))
            data['binance_api_secret'] = decrypt_data(data.get('binance_api_secret', ''))
        return data

    def update_user_api_keys(self, uid: str, api_key: str, api_secret: str):
        """Kullanıcının şifrelenmiş API anahtarlarını günceller."""
        user_ref = self.get_user_ref(uid)
        user_ref.update({
            'binance_api_key': encrypt_data(api_key),
            'binance_api_secret': encrypt_data(api_secret)
        })
        logger.info("API keys updated", user_id=uid)

    @robust_firebase_call(max_attempts=2)
    def log_trade(self, uid: str, trade_data: dict):
        """Kullanıcının işlem verilerini Realtime Database'e kaydeder."""
        trades_ref = self.get_trades_ref(uid)
        # Eğer timestamp datetime objesiyse ISO formatına çevir
        if 'timestamp' in trade_data and isinstance(trade_data['timestamp'], datetime):
            trade_data['timestamp'] = trade_data['timestamp'].isoformat()
        trades_ref.push(trade_data) # Firebase'de benzersiz anahtar ile ekle
        logger.info("Trade logged", user_id=uid, pnl=trade_data.get('pnl', 0))

    @robust_firebase_call(max_attempts=2)
    async def is_subscription_active(self, uid: str) -> bool:
        """Kullanıcının aboneliğinin aktif olup olmadığını kontrol eder."""
        user_data = self.get_user_ref(uid).get()
        if not user_data or 'subscription_expiry' not in user_data:
            return False
        try:
            # ISO formatından datetime objesine çevir
            expiry_date = datetime.fromisoformat(user_data['subscription_expiry'])
            # Aboneliğin bitiş tarihi UTC saat diliminde olmalı ve şimdiki zamanı UTC ile karşılaştır
            current_utc_time = datetime.now(timezone.utc)
            
            if current_utc_time > expiry_date:
                # Abonelik süresi dolmuşsa durumu güncelle
                if user_data.get('subscription_status') != 'expired':
                     self.get_user_ref(uid).update({'subscription_status': 'expired'})
                return False
            return True
        except ValueError:
            # Tarih ayrıştırma hatası olursa aboneliği aktif sayma
            logger.warning("Invalid subscription expiry date format", user_id=uid)
            return False
    
    def is_subscription_active_by_data(self, user_data: dict) -> bool:
        """
        User data'dan abonelik durumunu kontrol eder (admin panel için)
        """
        if not user_data or 'subscription_expiry' not in user_data:
            return False
        try:
            expiry_date = datetime.fromisoformat(user_data['subscription_expiry'])
            current_utc_time = datetime.now(timezone.utc)
            return current_utc_time <= expiry_date
        except ValueError:
            return False

# FirebaseManager sınıfının tek bir örneği oluşturulur.
firebase_manager = FirebaseManager()
