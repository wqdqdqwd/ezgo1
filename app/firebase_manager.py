import firebase_admin
from firebase_admin import credentials, db, auth
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from app.config import settings
from app.utils.logger import get_logger
from app.utils.encryption import encrypt_string, decrypt_string

logger = get_logger("firebase_manager")

class FirebaseManager:
    def __init__(self):
        self.initialized = False
        self.db_ref = None
        self._initialize_firebase()

    def _initialize_firebase(self):
        """Firebase Admin SDK'yı başlatır"""
        try:
            if not firebase_admin._apps:
                cred_json_str = settings.FIREBASE_CREDENTIALS_JSON
                database_url = settings.FIREBASE_DATABASE_URL
                
                if not cred_json_str or not database_url:
                    logger.error("Firebase credentials veya database URL eksik")
                    return
                
                # JSON string'i dict'e çevir
                cred_dict = json.loads(cred_json_str)
                cred = credentials.Certificate(cred_dict)
                
                # Firebase Admin SDK'yı başlat
                firebase_admin.initialize_app(cred, {'databaseURL': database_url})
                logger.info("Firebase Admin SDK başarıyla başlatıldı")
            
            # Database referansını ayarla
            self.db_ref = db.reference()
            self.initialized = True
            logger.info("Firebase Manager başarıyla başlatıldı")
            
        except Exception as e:
            logger.error(f"Firebase başlatma hatası: {e}")
            self.initialized = False

    def verify_token(self, id_token: str) -> Optional[dict]:
        """Firebase ID token'ını doğrular - SYNC METHOD"""
        try:
            if not self.initialized:
                logger.error("Firebase Manager başlatılmamış")
                return None
            
            # Token'ı doğrula
            decoded_token = auth.verify_id_token(id_token)
            
            if not decoded_token:
                logger.warning("Token doğrulama başarısız")
                return None
            
            uid = decoded_token.get('uid')
            if not uid:
                logger.warning("Token'da UID bulunamadı")
                return None
            
            # Kullanıcının veritabanında olup olmadığını kontrol et
            user_data = self.get_user_data(uid)
            if user_data:
                # Admin rolünü kontrol et
                decoded_token['admin'] = user_data.get('role') == 'admin'
                
            logger.debug(f"Token başarıyla doğrulandı: {uid}")
            return decoded_token
            
        except Exception as e:
            logger.error(f"Token doğrulama hatası: {e}")
            return None

    def create_user_record(self, uid: str, email: str) -> dict:
        """Yeni kullanıcı kaydı oluşturur"""
        try:
            if not self.initialized:
                raise Exception("Firebase Manager başlatılmamış")
            
            # Kullanıcı zaten var mı kontrol et
            existing_user = self.get_user_data(uid)
            if existing_user:
                logger.info(f"Kullanıcı zaten mevcut: {email}")
                return existing_user
            
            # Admin rolü kontrolü
            is_admin = email == settings.ADMIN_EMAIL
            
            user_data = {
                'uid': uid,
                'email': email,
                'role': 'admin' if is_admin else 'user',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'subscription_status': 'trial' if not is_admin else 'premium',
                'subscription_expiry': (datetime.now(timezone.utc) + timedelta(days=7 if not is_admin else 365)).isoformat(),
                'last_login': datetime.now(timezone.utc).isoformat(),
                'binance_api_key': None,
                'binance_api_secret': None
            }
            
            # Kullanıcıyı database'e kaydet
            self.db_ref.child('users').child(uid).set(user_data)
            
            logger.info(f"Yeni kullanıcı kaydedildi: {email}, Admin: {is_admin}")
            return user_data
            
        except Exception as e:
            logger.error(f"Kullanıcı kaydı hatası: {e}")
            raise e

    def get_user_data(self, uid: str) -> Optional[dict]:
        """Kullanıcı verilerini getirir"""
        try:
            if not self.initialized:
                return None
            
            user_ref = self.db_ref.child('users').child(uid)
            user_data = user_ref.get()
            
            return user_data if user_data else None
            
        except Exception as e:
            logger.error(f"Kullanıcı verisi getirme hatası: {e}")
            return None

    def update_user_api_keys(self, uid: str, api_key: str, api_secret: str) -> bool:
        """Kullanıcının Binance API anahtarlarını günceller (şifreleyerek)"""
        try:
            if not self.initialized:
                return False
            
            # API anahtarlarını şifrele
            encrypted_api_key = encrypt_string(api_key)
            encrypted_api_secret = encrypt_string(api_secret)
            
            # Database'e kaydet
            user_ref = self.db_ref.child('users').child(uid)
            user_ref.update({
                'binance_api_key': encrypted_api_key,
                'binance_api_secret': encrypted_api_secret,
                'api_keys_updated_at': datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"API anahtarları güncellendi: {uid}")
            return True
            
        except Exception as e:
            logger.error(f"API anahtarları güncelleme hatası: {e}")
            return False

    def get_decrypted_api_keys(self, uid: str) -> tuple:
        """Kullanıcının şifrelenmiş API anahtarlarını çözer ve döndürür"""
        try:
            user_data = self.get_user_data(uid)
            if not user_data:
                return None, None
            
            encrypted_api_key = user_data.get('binance_api_key')
            encrypted_api_secret = user_data.get('binance_api_secret')
            
            if not encrypted_api_key or not encrypted_api_secret:
                return None, None
            
            # Şifreyi çöz
            api_key = decrypt_string(encrypted_api_key)
            api_secret = decrypt_string(encrypted_api_secret)
            
            return api_key, api_secret
            
        except Exception as e:
            logger.error(f"API anahtarları çözme hatası: {e}")
            return None, None

    def is_subscription_active(self, uid: str) -> bool:
        """Kullanıcının aboneliğinin aktif olup olmadığını kontrol eder - SYNC METHOD"""
        try:
            user_data = self.get_user_data(uid)
            if not user_data:
                return False
            
            return self.is_subscription_active_by_data(user_data)
            
        except Exception as e:
            logger.error(f"Abonelik kontrolü hatası: {e}")
            return False

    def is_subscription_active_by_data(self, user_data: dict) -> bool:
        """Kullanıcı verisinden abonelik durumunu kontrol eder"""
        try:
            # Admin kullanıcıları her zaman aktif
            if user_data.get('role') == 'admin':
                return True
            
            subscription_status = user_data.get('subscription_status')
            subscription_expiry = user_data.get('subscription_expiry')
            
            if subscription_status == 'premium' and subscription_expiry:
                expiry_date = datetime.fromisoformat(subscription_expiry.replace('Z', '+00:00'))
                return datetime.now(timezone.utc) < expiry_date
            
            return False
            
        except Exception as e:
            logger.error(f"Abonelik veri kontrolü hatası: {e}")
            return False

    def extend_subscription(self, uid: str, days: int) -> bool:
        """Kullanıcının aboneliğini uzatır"""
        try:
            if not self.initialized:
                return False
            
            user_ref = self.db_ref.child('users').child(uid)
            current_data = user_ref.get()
            
            if not current_data:
                return False
            
            # Mevcut abonelik bitiş tarihini al veya şimdiki zamanı kullan
            current_expiry = current_data.get('subscription_expiry')
            if current_expiry:
                try:
                    expiry_date = datetime.fromisoformat(current_expiry.replace('Z', '+00:00'))
                    # Eğer abonelik henüz bitmemişse, mevcut tarihten uzat
                    if expiry_date > datetime.now(timezone.utc):
                        new_expiry = expiry_date + timedelta(days=days)
                    else:
                        new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
                except:
                    new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
            else:
                new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
            
            # Abonelik bilgilerini güncelle
            user_ref.update({
                'subscription_status': 'premium',
                'subscription_expiry': new_expiry.isoformat(),
                'subscription_extended_at': datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"Abonelik uzatıldı: {uid}, {days} gün")
            return True
            
        except Exception as e:
            logger.error(f"Abonelik uzatma hatası: {e}")
            return False

    def update_user_login(self, uid: str):
        """Kullanıcının son giriş zamanını günceller"""
        try:
            if not self.initialized:
                return
            
            user_ref = self.db_ref.child('users').child(uid)
            user_ref.update({
                'last_login': datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.warning(f"Son giriş zamanı güncelleme hatası: {e}")

    def log_trade(self, uid: str, trade_data: dict):
        """Kullanıcının işlemlerini loglar"""
        try:
            if not self.initialized:
                return
            
            # Timestamp'i ISO formatına çevir
            if 'timestamp' in trade_data and isinstance(trade_data['timestamp'], datetime):
                trade_data['timestamp'] = trade_data['timestamp'].isoformat()
            
            # User ID'yi ekle
            trade_data['user_id'] = uid
            
            # İşlemi kaydet
            trades_ref = self.db_ref.child('trades').child(uid)
            trades_ref.push(trade_data)
            
            logger.debug(f"İşlem kaydedildi: {uid}")
            
        except Exception as e:
            logger.error(f"İşlem kaydetme hatası: {e}")

    def get_all_users(self) -> dict:
        """Admin için tüm kullanıcıları getirir"""
        try:
            if not self.initialized:
                return {}
            
            users_ref = self.db_ref.child('users')
            users_data = users_ref.get()
            
            return users_data if users_data else {}
            
        except Exception as e:
            logger.error(f"Tüm kullanıcıları getirme hatası: {e}")
            return {}

    def get_user_trades(self, uid: str, limit: int = 100) -> list:
        """Kullanıcının işlem geçmişini getirir"""
        try:
            if not self.initialized:
                return []
            
            trades_ref = self.db_ref.child('trades').child(uid)
            trades_data = trades_ref.order_by_key().limit_to_last(limit).get()
            
            if not trades_data:
                return []
            
            # List formatına çevir
            trades_list = []
            for trade_id, trade_data in trades_data.items():
                trade_data['trade_id'] = trade_id
                trades_list.append(trade_data)
            
            # Tarihe göre sırala (en yeni önce)
            trades_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return trades_list
            
        except Exception as e:
            logger.error(f"Kullanıcı işlemleri getirme hatası: {e}")
            return []

# Global instance
firebase_manager = FirebaseManager()
