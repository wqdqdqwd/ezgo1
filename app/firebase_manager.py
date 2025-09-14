import firebase_admin
from firebase_admin import credentials, db, auth
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.utils.crypto import encrypt_data, decrypt_data
import json
from typing import Optional, Dict, Any
from app.utils.logger import get_logger
from app.utils.error_handler import robust_firebase_call

logger = get_logger("firebase_manager")

class FirebaseManager:
    def __init__(self):
        self.initialized = False
        try:
            if not firebase_admin._apps:  # Firebase uygulamasının zaten başlatılıp başlatılmadığını kontrol et
                if not settings.FIREBASE_CREDENTIALS_JSON or not settings.FIREBASE_DATABASE_URL:
                    raise ValueError("Firebase kimlik bilgileri (JSON veya Database URL) ayarlanmamış.")
                
                # FIREBASE_CREDENTIALS_JSON bir string olduğu için JSON'a ayrıştır
                try:
                    cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                except json.JSONDecodeError as e:
                    logger.error(f"Firebase credentials JSON parse error: {e}")
                    raise ValueError("Firebase credentials JSON formatı geçersiz.")
                
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': settings.FIREBASE_DATABASE_URL
                })
                
            self.initialized = True
            logger.info("Firebase Admin SDK initialized successfully")
            
        except Exception as e:
            logger.critical("Firebase initialization failed", error=str(e))
            self.initialized = False
            raise e 

    def _check_initialization(self):
        """Firebase'in başlatılıp başlatılmadığını kontrol eder"""
        if not self.initialized:
            raise RuntimeError("Firebase Manager not properly initialized")

    
    
        """
        Firebase ID Token'ı doğrular ve decoded payload'u döndürür.
        Bu payload kullanıcının UID'si ve custom claims'leri (örn. 'admin': True) içerir.
        
        NOT: Firebase auth.verify_id_token sync bir metoddur, async yapılmasına gerek yoktur.
        """
        self._check_initialization()
        try:
            if not token or not token.strip():
                logger.warning("Empty token provided for verification")
                return None
                
            decoded_token = auth.verify_id_token(token)
            logger.debug(f"Token verified successfully for user: {decoded_token.get('uid', 'unknown')}")
            return decoded_token
            
        except auth.InvalidIdTokenError as e:
            logger.warning(f"Invalid ID token: {e}")
            return None
        except auth.ExpiredIdTokenError as e:
            logger.warning(f"Expired ID token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return None

    def get_user_ref(self, uid: str):
        """Belirli bir kullanıcı için Realtime Database referansı döndürür."""
        self._check_initialization()
        if not uid:
            raise ValueError("User UID cannot be empty")
        return db.reference(f'users/{uid}')

    def get_trades_ref(self, uid: str):
        """Belirli bir kullanıcının işlem geçmişi için Realtime Database referansı döndürür."""
        self._check_initialization()
        if not uid:
            raise ValueError("User UID cannot be empty")
        return db.reference(f'trades/{uid}')

    @robust_firebase_call(max_attempts=3)
    def create_user_record(self, uid: str, email: str) -> Dict:
        """
        Yeni bir Firebase kullanıcısı için Realtime Database'de kayıt oluşturur.
        Rol ataması settings.ADMIN_EMAIL'e göre yapılır, ancak admin yetkisi 
        için Firebase Custom Claims'in ayrıca atanması gerektiğini unutmayın.
        """
        self._check_initialization()
        
        if not uid or not email:
            raise ValueError("UID and email are required")
            
        try:
            user_ref = self.get_user_ref(uid)
            trial_end_date = datetime.now(timezone.utc) + timedelta(days=7)
            
            # Admin email kontrolü (case insensitive)
            user_role_in_db = 'admin' if email and email.lower() == settings.ADMIN_EMAIL.lower() else 'user'

            user_data = {
                'uid': uid,
                'email': email,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'subscription_status': 'trial',
                'subscription_expiry': trial_end_date.isoformat(),
                'binance_api_key': '',  # Başlangıçta boş
                'binance_api_secret': '',  # Başlangıçta boş
                'role': user_role_in_db,  # Sadece Realtime DB'de gösterim için
                'last_login': datetime.now(timezone.utc).isoformat()
            }
            
            user_ref.set(user_data)
            logger.info("New user record created", email=email, uid=uid, role=user_role_in_db)
            return user_data
            
        except Exception as e:
            logger.error(f"Failed to create user record for {uid}: {e}")
            raise

    @robust_firebase_call(max_attempts=2)
    
        """
        Belirli bir kullanıcının Realtime Database'deki verilerini çeker
        ve API anahtarlarını çözer (decrypt eder).
        """
        self._check_initialization()
        
        if not uid:
            logger.warning("Empty UID provided to get_user_data")
            return None
            
        try:
            user_ref = self.get_user_ref(uid)
            data = user_ref.get()
            
            if not data:
                logger.warning(f"No user data found for UID: {uid}")
                return None
            
            # API anahtarlarını çöz (decrypt)
            encrypted_api_key = data.get('binance_api_key', '')
            encrypted_api_secret = data.get('binance_api_secret', '')
            
            if encrypted_api_key:
                try:
                    data['binance_api_key'] = decrypt_data(encrypted_api_key)
                except Exception as e:
                    logger.error(f"Failed to decrypt API key for user {uid}: {e}")
                    data['binance_api_key'] = ''
            
            if encrypted_api_secret:
                try:
                    data['binance_api_secret'] = decrypt_data(encrypted_api_secret)
                except Exception as e:
                    logger.error(f"Failed to decrypt API secret for user {uid}: {e}")
                    data['binance_api_secret'] = ''
            
            logger.debug(f"User data retrieved for UID: {uid}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get user data for {uid}: {e}")
            return None

    @robust_firebase_call(max_attempts=3)
    def update_user_api_keys(self, uid: str, api_key: str, api_secret: str) -> bool:
        """Kullanıcının şifrelenmiş API anahtarlarını günceller."""
        self._check_initialization()
        
        if not uid or not api_key or not api_secret:
            raise ValueError("UID, API key, and API secret are required")
            
        try:
            # API anahtarlarını şifrele
            encrypted_api_key = encrypt_data(api_key)
            encrypted_api_secret = encrypt_data(api_secret)
            
            user_ref = self.get_user_ref(uid)
            user_ref.update({
                'binance_api_key': encrypted_api_key,
                'binance_api_secret': encrypted_api_secret,
                'api_keys_updated_at': datetime.now(timezone.utc).isoformat()
            })
            
            logger.info("API keys updated successfully", user_id=uid)
            return True
            
        except Exception as e:
            logger.error(f"Failed to update API keys for user {uid}: {e}")
            return False

    @robust_firebase_call(max_attempts=2)
    def log_trade(self, uid: str, trade_data: Dict[str, Any]) -> bool:
        """Kullanıcının işlem verilerini Realtime Database'e kaydeder."""
        self._check_initialization()
        
        if not uid or not trade_data:
            logger.warning("Empty UID or trade_data provided to log_trade")
            return False
            
        try:
            # Trade data'yı kopyala ve timestamp'i kontrol et
            trade_copy = trade_data.copy()
            
            # Timestamp'i ISO formatına çevir
            if 'timestamp' in trade_copy:
                if isinstance(trade_copy['timestamp'], datetime):
                    trade_copy['timestamp'] = trade_copy['timestamp'].isoformat()
            else:
                trade_copy['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # User ID'yi de ekle
            trade_copy['user_id'] = uid
            
            trades_ref = self.get_trades_ref(uid)
            result = trades_ref.push(trade_copy)  # Firebase'de benzersiz anahtar ile ekle
            
            logger.info("Trade logged successfully", 
                       user_id=uid, 
                       pnl=trade_copy.get('pnl', 0),
                       symbol=trade_copy.get('symbol', 'Unknown'))
            return True
            
        except Exception as e:
            logger.error(f"Failed to log trade for user {uid}: {e}")
            return False

    def is_subscription_active(self, uid: str) -> bool:
        """
        Kullanıcının aboneliğinin aktif olup olmadığını kontrol eder.
        
        NOT: Bu metod sync yapıldı çünkü Firebase Realtime Database sync çalışır.
        """
        self._check_initialization()
        
        if not uid:
            logger.warning("Empty UID provided to is_subscription_active")
            return False
            
        try:
            user_ref = self.get_user_ref(uid)
            user_data = user_ref.get()
            
            if not user_data or 'subscription_expiry' not in user_data:
                logger.warning(f"No subscription data found for user: {uid}")
                return False
                
            # ISO formatından datetime objesine çevir
            try:
                expiry_str = user_data['subscription_expiry']
                
                # Farklı datetime formatlarını destekle
                try:
                    expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                except ValueError:
                    # Alternatif format dene
                    expiry_date = datetime.fromisoformat(expiry_str)
                
                # Timezone bilgisi yoksa UTC olarak kabul et
                if expiry_date.tzinfo is None:
                    expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                
                # Şimdiki zaman ile karşılaştır
                current_utc_time = datetime.now(timezone.utc)
                is_active = current_utc_time <= expiry_date
                
                # Abonelik süresi dolmuşsa durumu güncelle
                if not is_active and user_data.get('subscription_status') != 'expired':
                    try:
                        user_ref.update({'subscription_status': 'expired'})
                        logger.info(f"Subscription expired for user: {uid}")
                    except Exception as e:
                        logger.error(f"Failed to update expired subscription status: {e}")
                
                logger.debug(f"Subscription check for {uid}: {is_active}")
                return is_active
                
            except ValueError as e:
                logger.warning(f"Invalid subscription expiry date format for user {uid}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to check subscription status for user {uid}: {e}")
            return False
    
    def is_subscription_active_by_data(self, user_data: Dict) -> bool:
        """
        User data'dan abonelik durumunu kontrol eder (admin panel için)
        """
        if not user_data or 'subscription_expiry' not in user_data:
            return False
            
        try:
            expiry_str = user_data['subscription_expiry']
            
            # Farklı datetime formatlarını destekle
            try:
                expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
            except ValueError:
                expiry_date = datetime.fromisoformat(expiry_str)
            
            # Timezone bilgisi yoksa UTC olarak kabul et
            if expiry_date.tzinfo is None:
                expiry_date = expiry_date.replace(tzinfo=timezone.utc)
            
            current_utc_time = datetime.now(timezone.utc)
            return current_utc_time <= expiry_date
            
        except ValueError as e:
            logger.warning(f"Invalid subscription expiry date in user data: {e}")
            return False

    @robust_firebase_call(max_attempts=2)
    def extend_subscription(self, uid: str, days: int = 30) -> bool:
        """Kullanıcının aboneliğini belirtilen gün kadar uzatır"""
        self._check_initialization()
        
        if not uid or days <= 0:
            raise ValueError("Valid UID and positive days are required")
            
        try:
            user_ref = self.get_user_ref(uid)
            user_data = user_ref.get()
            
            if not user_data:
                logger.error(f"User not found for subscription extension: {uid}")
                return False
            
            # Mevcut abonelik bitiş tarihi
            current_expiry = user_data.get('subscription_expiry')
            if current_expiry:
                try:
                    expiry_date = datetime.fromisoformat(current_expiry.replace('Z', '+00:00'))
                except ValueError:
                    expiry_date = datetime.fromisoformat(current_expiry)
                    
                if expiry_date.tzinfo is None:
                    expiry_date = expiry_date.replace(tzinfo=timezone.utc)
            else:
                # Eğer mevcut abonelik yoksa şimdiden başlat
                expiry_date = datetime.now(timezone.utc)
            
            # Yeni bitiş tarihi hesapla
            new_expiry = expiry_date + timedelta(days=days)
            
            # Abonelik durumunu güncelle
            updates = {
                'subscription_expiry': new_expiry.isoformat(),
                'subscription_status': 'active',
                'subscription_extended_at': datetime.now(timezone.utc).isoformat()
            }
            
            user_ref.update(updates)
            
            logger.info(f"Subscription extended for user {uid} by {days} days until {new_expiry}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to extend subscription for user {uid}: {e}")
            return False

    def get_all_users(self) -> Dict:
        """Tüm kullanıcıları döndürür (admin için)"""
        self._check_initialization()
        
        try:
            users_ref = db.reference('users')
            users_data = users_ref.get()
            
            if not users_data:
                logger.info("No users found in database")
                return {}
            
            # API anahtarlarını kaldır (güvenlik için)
            filtered_users = {}
            for uid, user_data in users_data.items():
                if isinstance(user_data, dict):
                    filtered_data = user_data.copy()
                    filtered_data.pop('binance_api_key', None)
                    filtered_data.pop('binance_api_secret', None)
                    filtered_users[uid] = filtered_data
            
            logger.info(f"Retrieved {len(filtered_users)} users")
            return filtered_users
            
        except Exception as e:
            logger.error(f"Failed to get all users: {e}")
            return {}

    def update_user_login(self, uid: str) -> bool:
        """Kullanıcının son giriş zamanını günceller"""
        self._check_initialization()
        
        if not uid:
            return False
            
        try:
            user_ref = self.get_user_ref(uid)
            user_ref.update({
                'last_login': datetime.now(timezone.utc).isoformat()
            })
            return True
        except Exception as e:
            logger.error(f"Failed to update login time for user {uid}: {e}")
            return False

# FirebaseManager sınıfının tek bir örneği oluşturulur.
firebase_manager = FirebaseManager()
