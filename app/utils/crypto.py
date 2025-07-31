from cryptography.fernet import Fernet
from app.config import settings

# ENCRYPTION_KEY'in varlığını kontrol et, yoksa programı başlatma
if not settings.ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY ortam değişkeni ayarlanmamış. Lütfen .env dosyanızı kontrol edin.")

# Şifreleme anahtarını kullanarak Fernet nesnesini bir kere oluştur
cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_data(data: str) -> str:
    """
    Verilen metni (string) şifreler.
    Args:
        data (str): Şifrelenecek metin.
    Returns:
        str: Şifrelenmiş metin.
    """
    if not data:
        return ""
    encrypted_text = cipher_suite.encrypt(data.encode('utf-8'))
    return encrypted_text.decode('utf-8')

def decrypt_data(encrypted_data: str) -> str:
    """
    Şifrelenmiş metni çözer.
    Args:
        encrypted_data (str): Çözülecek şifreli metin.
    Returns:
        str: Orjinal, çözülmüş metin.
    """
    if not encrypted_data:
        return ""
    try:
        decrypted_text = cipher_suite.decrypt(encrypted_data.encode('utf-8'))
        return decrypted_text.decode('utf-8')
    except Exception as e:
        # Şifre çözme hatası durumunda (örneğin anahtar değiştiyse) boş string döndür
        print(f"Şifre çözme hatası: {e}")
        return ""
