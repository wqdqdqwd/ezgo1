import asyncio
import time
import json
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from functools import wraps
import logging

from app.bot_manager import bot_manager
from app.config import settings
from app.firebase_manager import firebase_manager, db

# Simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Statik klasörün doğru yolunu belirleme
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_FOLDER)

# CORS setup
CORS(app, 
     origins=["*"] if settings.ENVIRONMENT == "DEVELOPMENT" else [
         "https://ezyago.com",
         "https://www.ezyago.com"
     
     ])

# Request logging middleware
@app.before_request
def log_request():
    app.logger.info(f"{request.method} {request.path}")

@app.after_request
def log_response(response):
    app.logger.info(f"{request.method} {request.path} - {response.status_code}")
    return response

# Helper functions for validation
def validate_start_request(data):
    """Validate bot start request"""
    required_fields = ['symbol', 'timeframe', 'leverage', 'order_size', 'stop_loss', 'take_profit']
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing field: {field}"
    
    # Basic validation
    if not data['symbol'].endswith('USDT'):
        return False, "Invalid symbol"
    
    if data['leverage'] < 1 or data['leverage'] > 125:
        return False, "Leverage must be between 1 and 125"
    
    if data['order_size'] < 10 or data['order_size'] > 10000:
        return False, "Order size must be between 10 and 10000"
    
    if data['take_profit'] <= data['stop_loss']:
        return False, "Take profit must be greater than stop loss"
    
    return True, None

def validate_api_keys(data):
    """Validate API keys"""
    if 'api_key' not in data or 'api_secret' not in data:
        return False, "Missing API key or secret"
    
    if len(data['api_key']) < 60 or len(data['api_secret']) < 60:
        return False, "Invalid API key format"
    
    return True, None

# Authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        
        token = auth_header.split(' ')[1]
        try:
            user_payload = firebase_manager.verify_token(token)
            if not user_payload:
                return jsonify({"error": "Invalid token"}), 401
            
            uid = user_payload['uid']
            
            # Get or create user data
            user_data = firebase_manager.get_user_data(uid)
            if not user_data:
                user_data = firebase_manager.create_user_record(uid, user_payload.get('email', ''))
            
            user_data['uid'] = uid
            user_data['role'] = 'admin' if user_payload.get('admin', False) else 'user'
            
            # Add user to request context
            request.current_user = user_data
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return jsonify({"error": "Authentication failed"}), 401
    
    return decorated_function

def require_subscription(f):
    @wraps(f)
    @require_auth
    def decorated_function(*args, **kwargs):
        if not firebase_manager.is_subscription_active(request.current_user['uid']):
            return jsonify({"error": "Active subscription required"}), 403
        return f(*args, **kwargs)
    
    return decorated_function

def require_admin(f):
    @wraps(f)
    @require_auth
    def decorated_function(*args, **kwargs):
        if request.current_user.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    
    return decorated_function

# API Routes
@app.route('/api/firebase-config', methods=['GET'])
def get_firebase_config():
    """Frontend için Firebase yapılandırması"""
    return jsonify({
        "apiKey": settings.FIREBASE_WEB_API_KEY,
        "authDomain": settings.FIREBASE_WEB_AUTH_DOMAIN,
        "databaseURL": settings.FIREBASE_DATABASE_URL,
        "projectId": settings.FIREBASE_WEB_PROJECT_ID,
        "storageBucket": settings.FIREBASE_WEB_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_WEB_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_WEB_APP_ID,
    })

@app.route('/api/start', methods=['POST'])
@require_subscription
def start_bot():
    """Botu başlatır"""
    try:
        data = request.get_json()
        
        # Validate request
        is_valid, error_msg = validate_start_request(data)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        user = request.current_user
        logger.info(f"Bot start requested for user {user['uid']}, symbol {data['symbol']}")
        
        # Save user settings
        save_user_settings_sync(user['uid'], {
            'symbol': data['symbol'],
            'leverage': data['leverage'],
            'orderSize': data['order_size'],
            'tp': data['take_profit'],
            'sl': data['stop_loss'],
            'timeframe': data['timeframe']
        })
        
        # Create simple request object for bot manager
        class SimpleRequest:
            def __init__(self, data):
                self.symbol = data['symbol']
                self.timeframe = data['timeframe']
                self.leverage = data['leverage']
                self.order_size = data['order_size']
                self.stop_loss = data['stop_loss']
                self.take_profit = data['take_profit']
            
            def dict(self):
                return {
                    'symbol': self.symbol,
                    'timeframe': self.timeframe,
                    'leverage': self.leverage,
                    'order_size': self.order_size,
                    'stop_loss': self.stop_loss,
                    'take_profit': self.take_profit
                }
        
        simple_request = SimpleRequest(data)
        
        # Start bot using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(bot_manager.start_bot_for_user(user['uid'], simple_request))
        finally:
            loop.close()
        
        if "error" in result:
            logger.error(f"Bot start failed for user {user['uid']}: {result['error']}")
            return jsonify({"error": result["error"]}), 400
        
        logger.info(f"Bot started successfully for user {user['uid']}")
        return jsonify({"success": True, **result})
    
    except Exception as e:
        logger.error(f"Unexpected error in bot start: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/stop', methods=['POST'])
@require_auth
def stop_bot():
    """Botu durdurur"""
    try:
        user = request.current_user
        logger.info(f"Bot stop requested for user {user['uid']}")
        
        # Stop bot using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(bot_manager.stop_bot_for_user(user['uid']))
        finally:
            loop.close()
        
        if "error" in result:
            logger.error(f"Bot stop failed for user {user['uid']}: {result['error']}")
            return jsonify({"error": result["error"]}), 400
        
        logger.info(f"Bot stopped successfully for user {user['uid']}")
        return jsonify({"success": True, **result})
    
    except Exception as e:
        logger.error(f"Unexpected error in bot stop: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/status', methods=['GET'])
@require_auth
def get_status():
    """Bot durumunu alır"""
    user = request.current_user
    status = bot_manager.get_bot_status(user['uid'])
    
    return jsonify({
        "is_running": status.get("is_running", False),
        "status_message": status.get("status_message", "Bot durumu bilinmiyor"),
        "symbol": status.get("symbol"),
        "position_side": status.get("position_side"),
        "last_check_time": status.get("last_check_time")
    })

@app.route('/api/save-user-settings', methods=['POST'])
@require_auth
def save_user_settings_endpoint():
    """Kullanıcı ayarlarını kaydeder"""
    try:
        data = request.get_json()
        if 'settings' not in data:
            return jsonify({"error": "Missing settings"}), 400
        
        user = request.current_user
        save_user_settings_sync(user['uid'], data['settings'])
        return jsonify({"success": True, "message": "Ayarlar kaydedildi"})
    
    except Exception as e:
        logger.error(f"Error saving user settings: {e}")
        return jsonify({"error": "Failed to save settings"}), 500

def save_user_settings_sync(uid, settings):
    """İç kullanım için ayar kaydetme fonksiyonu"""
    user_ref = firebase_manager.get_user_ref(uid)
    user_ref.update({
        'settings': settings,
        'settings_updated_at': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/trading-stats', methods=['GET'])
@require_auth
def get_trading_stats():
    """Trading istatistiklerini alır"""
    try:
        user = request.current_user
        trades_ref = firebase_manager.get_trades_ref(user['uid'])
        trades_data = trades_ref.get() or {}
        
        # İstatistikleri hesapla
        stats = calculate_trading_stats(trades_data)
        
        return jsonify({
            "success": True,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Trading stats calculation error: {e}")
        return jsonify({
            "success": False,
            "stats": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "uptime_hours": 0.0
            }
        })

def calculate_trading_stats(trades_data):
    """Trading verilerinden istatistik hesaplar"""
    if not trades_data:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "uptime_hours": 0.0
        }
    
    total_trades = len(trades_data)
    total_pnl = 0.0
    winning_trades = 0
    losing_trades = 0
    
    for trade_id, trade in trades_data.items():
        pnl = trade.get('pnl', 0.0)
        total_pnl += pnl
        
        if pnl > 0:
            winning_trades += 1
        elif pnl < 0:
            losing_trades += 1
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    uptime_hours = total_trades * 0.5
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 1),
        "uptime_hours": round(uptime_hours, 1)
    }

@app.route('/api/user-profile', methods=['GET'])
@require_auth
def get_user_profile():
    """Kullanıcı profil bilgileri"""
    user = request.current_user
    bot_status = bot_manager.get_bot_status(user['uid'])
    
    # Trading istatistiklerini al
    try:
        trades_ref = firebase_manager.get_trades_ref(user['uid'])
        trades_data = trades_ref.get() or {}
        stats = calculate_trading_stats(trades_data)
    except Exception as e:
        logger.error(f"Stats calculation error: {e}")
        stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "uptime_hours": 0.0
        }
    
    # Kullanıcı ayarlarını al
    user_settings = user.get('settings', {
        'leverage': 10,
        'orderSize': 20,
        'tp': 4,
        'sl': 2,
        'symbol': 'BTCUSDT',
        'timeframe': '15m'
    })
    
    return jsonify({
        "email": user.get('email'),
        "subscription_status": user.get('subscription_status'),
        "subscription_expiry": user.get('subscription_expiry'),
        "registration_date": user.get('created_at'),
        "has_api_keys": bool(user.get('binance_api_key')),
        "payment_address": settings.PAYMENT_TRC20_ADDRESS,
        "is_admin": user.get('role') == 'admin',
        "server_ips": ["18.156.158.53", "18.156.42.200", "52.59.103.54"],
        "bot_last_check": bot_status.get("last_check_time"),
        "settings": user_settings,
        "stats": stats
    })

@app.route('/api/save-keys', methods=['POST'])
@require_auth
def save_api_keys():
    """API anahtarlarını kaydeder"""
    try:
        data = request.get_json()
        
        # Validate keys
        is_valid, error_msg = validate_api_keys(data)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        user = request.current_user
        logger.info(f"API keys save requested for user {user['uid']}")
        
        firebase_manager.update_user_api_keys(user['uid'], data['api_key'], data['api_secret'])
        
        logger.info(f"API keys saved successfully for user {user['uid']}")
        return jsonify({"success": True, "message": "API anahtarları güvenli şekilde kaydedildi"})
    except Exception as e:
        logger.error(f"Failed to save API keys: {e}")
        return jsonify({"error": "API anahtarları kaydedilemedi"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Sistem sağlık kontrolü"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "4.1.0",
            "components": {}
        }
        
        # Firebase health check
        try:
            db.reference('health').set({
                'last_check': datetime.now(timezone.utc).isoformat(),
                'status': 'healthy'
            })
            health_status["components"]["firebase"] = "healthy"
        except Exception as e:
            health_status["components"]["firebase"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # Bot manager health check
        try:
            active_bots = len(bot_manager.active_bots)
            health_status["components"]["bot_manager"] = "healthy"
            health_status["active_bots"] = active_bots
        except Exception as e:
            health_status["components"]["bot_manager"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        if health_status["status"] == "degraded":
            return jsonify(health_status), 503
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }), 503

# Admin routes
@app.route('/api/admin/users', methods=['GET'])
@require_admin
def get_all_users():
    """Admin için tüm kullanıcıları listeler"""
    try:
        all_users_data = db.reference('users').get() or {}
        
        sanitized_users = {}
        for uid, user_data in all_users_data.items():
            sanitized_users[uid] = {
                'email': user_data.get('email'),
                'subscription_status': user_data.get('subscription_status'),
                'subscription_expiry': user_data.get('subscription_expiry'),
                'created_at': user_data.get('created_at'),
                'role': user_data.get('role', 'user'),
                'has_api_keys': bool(user_data.get('binance_api_key') and user_data.get('binance_api_secret')),
                'total_trades': 0,
                'total_pnl': 0.0
            }
        
        return jsonify({"users": sanitized_users})
    except Exception as e:
        logger.error(f"Admin users list error: {e}")
        return jsonify({"error": "Kullanıcı listesi alınamadı"}), 500

@app.route('/api/admin/activate-subscription', methods=['POST'])
@require_admin
def activate_subscription():
    """Abonelik uzatır (Admin)"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400
        
        user_ref = firebase_manager.get_user_ref(user_id)
        user_data = user_ref.get()
        
        if not user_data:
            return jsonify({"error": "Kullanıcı bulunamadı"}), 404
        
        # 30 gün ekle
        new_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        
        user_ref.update({
            "subscription_status": "active",
            "subscription_expiry": new_expiry.isoformat(),
            "last_updated_by": request.current_user['email'],
            "last_updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        admin_email = request.current_user['email']
        logger.info(f"Admin {admin_email} extended subscription for {user_id}")
        return jsonify({
            "success": True, 
            "message": "Abonelik 30 gün uzatıldı", 
            "new_expiry": new_expiry.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Subscription extension error: {e}")
        return jsonify({"error": "Abonelik uzatılamadı"}), 500

# Static files
@app.route('/')
def index():
    """Ana sayfa"""
    return send_from_directory('static', 'index.html')

@app.route('/admin')
@require_admin
def admin_page():
    """Admin paneli"""
    return send_from_directory('static', 'admin.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    """Static dosyalar"""
    return send_from_directory('static', filename)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting EzyagoTrading Backend on port {port}")
    app.run(host='0.0.0.0', port=port, debug=settings.ENVIRONMENT == "DEVELOPMENT")
