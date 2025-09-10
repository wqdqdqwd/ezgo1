 
# 🚀 EzyagoTrading - Professional Crypto Trading Bot

Modern, güvenli ve kullanıcı dostu kripto para futures trading botu. 7 gün ücretsiz deneme ile başlayın!

## ✨ Özellikler

### 🎯 Trading Özellikleri
- **Gerçek Zamanlı Trading**: Binance Futures API entegrasyonu
- **EMA Crossover Stratejisi**: 9/21 EMA kesişim stratejisi
- **Risk Yönetimi**: Kullanıcı tanımlı Stop Loss ve Take Profit
- **Kaldıraç Kontrolü**: 1x-125x arası ayarlanabilir kaldıraç
- **Margin Tipi**: İzolated ve Cross margin desteği
- **Çoklu Timeframe**: 1m'den 1d'ye kadar tüm zaman dilimleri

### 🛡️ Güvenlik
- **API Anahtarı Şifreleme**: AES-256 şifreleme ile güvenli saklama
- **JWT Authentication**: Güvenli kullanıcı oturumu yönetimi
- **Firebase Integration**: Google Firebase ile güvenli veritabanı
- **Input Validation**: Kapsamlı veri doğrulama
- **Rate Limiting**: DDoS koruması

### 📱 Kullanıcı Deneyimi
- **Mobil-First Tasarım**: Responsive ve touch-friendly arayüz
- **Real-Time Updates**: WebSocket ile anlık güncellemeler
- **Professional UI**: Modern ve kullanıcı dostu arayüz
- **Dark Theme**: Göz yorgunluğunu azaltan koyu tema
- **Multi-Language**: Türkçe ve İngilizce dil desteği

### 💼 Abonelik Sistemi
- **7 Gün Ücretsiz Deneme**: Kredi kartı gerektirmez
- **Esnek Abonelik**: Aylık ödeme seçenekleri
- **Otomatik Yenileme**: Kesintisiz hizmet
- **Admin Paneli**: Kullanıcı yönetimi ve raporlama

## 🛠️ Teknoloji Yığını

### Backend
- **FastAPI**: Modern, hızlı Python web framework
- **WebSocket**: Gerçek zamanlı veri akışı
- **Firebase**: Authentication ve Firestore veritabanı
- **python-binance**: Binance API entegrasyonu
- **Cryptography**: Veri şifreleme
- **JWT**: Token tabanlı authentication

### Frontend
- **Vanilla JavaScript**: Hafif ve hızlı
- **CSS3**: Modern styling ve animasyonlar
- **WebSocket**: Real-time UI güncellemeleri
- **Responsive Design**: Mobil-first yaklaşım

### DevOps
- **Docker**: Containerization
- **uvicorn**: ASGI server
- **Nginx**: Reverse proxy (production)
- **Let's Encrypt**: SSL sertifikaları

## 📋 Gereksinimler

### Sistem Gereksinimleri
- Python 3.11+
- 512MB RAM (minimum)
- 1GB disk alanı
- Internet bağlantısı

### Servis Gereksinimleri
- Firebase projesi (ücretsiz plan yeterli)
- Binance hesabı (kullanıcılar için)
- Domain adı (production için)

## 🚀 Hızlı Kurulum

### 1. Projeyi İndirin
```bash
git clone https://github.com/your-repo/ezyago-trading.git
cd ezyago-trading
```

### 2. Python Sanal Ortamı Oluşturun
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate     # Windows
```

### 3. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Environment Değişkenlerini Ayarlayın
```bash
cp .env.example .env
# .env dosyasını kendi bilgilerinizle düzenleyin
```

### 5. Firebase Kurulumu
1. [Firebase Console](https://console.firebase.google.com)'a gidin
2. Yeni proje oluşturun
3. Authentication'ı etkinleştirin (Email/Password)
4. Firestore veritabanını etkinleştirin
5. Service Account anahtarını indirin
6. `.env` dosyasına Firebase bilgilerini ekleyin

### 6. Uygulamayı Başlatın
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Uygulama şu adreste çalışacak: http://localhost:8000

## 🐳 Docker ile Kurulum

### 1. Docker Image Oluşturun
```bash
docker build -t ezyago-trading .
```

### 2. Çalıştırın
```bash
docker run -d \
  --name ezyago-trading \
  -p 8000:8000 \
  --env-file .env \
  ezyago-trading
```

### 3. Docker Compose (Önerilen)
```bash
docker-compose up -d
```

## ⚙️ Konfigürasyon

### Güvenlik Anahtarları Oluşturma

```python
# JWT Secret oluşturmak için
import secrets
jwt_secret = secrets.token_urlsafe(64)
print(f"JWT_SECRET={jwt_secret}")

# Encryption Key oluşturmak için
from cryptography.fernet import Fernet
encryption_key = Fernet.generate_key().decode()
print(f"ENCRYPTION_KEY={encryption_key}")
```

### Firebase Konfigürasyonu

1. **Service Account Oluşturma:**
   - Firebase Console > Project Settings > Service Accounts
   - "Generate new private key" butonuna tıklayın
   - JSON dosyasını indirin

2. **Environment Değişkenleri:**
   ```bash
   FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json
   # veya
   FIREBASE_CREDENTIALS_JSON='{"type": "service_account", ...}'
   ```

3. **Firestore Rules:**
   ```javascript
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /users/{userId} {
         allow read, write: if request.auth != null && request.auth.uid == userId;
       }
       match /trades/{tradeId} {
         allow read, write: if request.auth != null;
       }
     }
   }
   ```

## 🌐 Production Deployment

### 1. Server Hazırlığı
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install nginx certbot python3-certbot-nginx
```

### 2. Nginx Konfigürasyonu
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. SSL Sertifikası
```bash
sudo certbot --nginx -d yourdomain.com
```

### 4. Systemd Service
```ini
[Unit]
Description=EzyagoTrading FastAPI app
After=network.target

[Service]
Type=exec
User=app
Group=app
WorkingDirectory=/app
Environment="PATH=/app/venv/bin"
ExecStart=/app/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 5. Process Manager (PM2 Alternatifi)
```bash
# PM2 ile çalıştırma
npm install -g pm2
pm2 start "uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2" --name ezyago-trading
pm2 startup
pm2 save
```

## 🔧 API Dokümantasyonu

### Authentication Endpoints

#### POST /api/auth/register
Yeni kullanıcı kaydı
```json
{
  "full_name": "Ahmet Yılmaz",
  "email": "ahmet@example.com", 
  "password": "123456"
}
```

#### POST /api/auth/login
Kullanıcı girişi
```json
{
  "email": "ahmet@example.com",
  "password": "123456"
}
```

### Bot Management Endpoints

#### POST /api/bot/start
Botu başlatır (Requires auth)
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "leverage": 5,
  "order_size_usdt": 35.0,
  "stop_loss_percent": 2.0,
  "take_profit_percent": 4.0,
  "margin_type": "isolated"
}
```

#### POST /api/bot/stop
Botu durdurur (Requires auth)

#### GET /api/bot/status
Bot durumunu getirir (Requires auth)

### User Management Endpoints

#### GET /api/user/profile
Kullanıcı profil bilgileri

#### POST /api/user/api-keys
API anahtarlarını kaydet
```json
{
  "api_key": "your_binance_api_key",
  "api_secret": "your_binance_api_secret"
}
```

## 📊 Monitoring & Logging

### Health Check
```bash
curl http://localhost:8000/api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "active_connections": 5,
  "active_bots": 2
}
```

### Logs
```bash
# Uygulama logları
tail -f logs/app.log

# Docker logları
docker logs -f ezyago-trading

# Systemd logları
journalctl -u ezyago-trading -f
```

## 🐛 Troubleshooting

### Yaygın Sorunlar

#### 1. Firebase Connection Error
```bash
# Çözüm: Firebase credentials kontrol edin
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

#### 2. WebSocket Connection Failed
```bash
# Çözüm: Firewall kurallarını kontrol edin
sudo ufw allow 8000
```

#### 3. Bot Start Failed
- API anahtarlarının doğru olduğundan emin olun
- Binance API'de futures trading izinlerini kontrol edin
- Internet bağlantısını kontrol edin

#### 4. High Memory Usage
```bash
# Memory kullanımını azaltmak için worker sayısını düşürün
uvicorn main:app --workers 1
```

### Debug Mode
```bash
# Debug modunda çalıştırma
ENVIRONMENT=DEVELOPMENT LOG_LEVEL=DEBUG uvicorn main:app --reload
```

## 🔒 Güvenlik Best Practices

### 1. API Anahtarları
- API anahtarlarını asla git'e commit etmeyin
- Production'da environment variables kullanın
- Regular olarak anahtarları rotate edin

### 2. Database Security
- Firestore rules'ları doğru ayarlayın
- Backup stratejiniz olsun
- User data encryption kullanın

### 3. Server Security
- Regular security updates
- Fail2ban kurulumu
- Strong password policies
- SSH key authentication

### 4. Application Security
- HTTPS zorunlu
- Security headers
- Rate limiting
- Input validation

## 📈 Performance Optimization

### 1. Database Optimization
- Firestore indexes optimize edin
- Query caching kullanın
- Connection pooling

### 2. WebSocket Optimization
- Connection limits ayarlayın
- Heartbeat intervals optimize edin
- Message queueing

### 3. API Optimization
- Response caching
- Gzip compression
- CDN kullanımı

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Bu proje MIT License altında lisanslanmıştır. Detaylar için `LICENSE` dosyasını inceleyiniz.

## 📞 Support

- **Email**: support@ezyagotrading.com
- **Documentation**: https://docs.ezyagotrading.com
- **Issues**: GitHub Issues
- **Discord**: https://discord.gg/ezyagotrading

## 🙏 Acknowledgments

- Binance API for trading functionality
- Firebase for authentication and database
- FastAPI for the excellent web framework
- The crypto trading community for feedback and ideas

---

## ⚠️ Risk Disclaimer

**UYARI**: Kripto para trading'i yüksek risk içerir ve tüm sermayenizi kaybedebilirsiniz. Bu yazılım sadece eğitim ve araştırma amaçlıdır. Yatırım kararlarınızın sorumluluğu tamamen size aittir. 

Bu bot'u kullanmadan önce:
- Kripto para risklerini tam olarak anlayın
- Sadece kaybetmeyi göze alabileceğiniz parayı yatırın
- Gerekirse profesyonel finansal danışmanlık alın
- Bot'un performansını düzenli olarak izleyin

**Finansal tavsiye değildir. Kendi araştırmanızı yapın.**
