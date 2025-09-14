from cryptography.fernet import Fernet
import base64
import os
from app.config import settings

def get_encryption_key():
    """Şifreleme anahtarını getirir veya oluşturur"""
    encryption_key = settings.ENCRYPTION_KEY
    
    if not encryption_key:
        # Yeni anahtar oluştur
        key = Fernet.generate_key()
        encryption_key = base64.urlsafe_b64encode(key).decode()
        print(f"YENİ ŞİFRELEME ANAHTARI: {encryption_key}")
        print("Bu anahtarı .env dosyanıza ENCRYPTION_KEY= olarak ekleyin!")
    
    return encryption_key.encode()

def encrypt_string(text: str) -> str:
    """String'i şifreler"""
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        encrypted_text = fernet.encrypt(text.encode())
        return base64.urlsafe_b64encode(encrypted_text).decode()
    except Exception as e:
        raise Exception(f"Şifreleme hatası: {e}")

def decrypt_string(encrypted_text: str) -> str:
    """Şifrelenmiş string'i çözer"""
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
        decrypted_text = fernet.decrypt(encrypted_bytes)
        return decrypted_text.decode()
    except Exception as e:
        raise Exception(f"Şifre çözme hatası: {e}")
