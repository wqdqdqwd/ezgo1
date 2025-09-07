from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
from typing import Dict, Any
from app.utils.logger import get_logger

logger = get_logger("metrics")

# Bot metrics
bot_starts_total = Counter('bot_starts_total', 'Total number of bot starts', ['user_id', 'symbol'])
bot_stops_total = Counter('bot_stops_total', 'Total number of bot stops', ['user_id', 'symbol', 'reason'])
active_bots = Gauge('active_bots', 'Number of currently active bots')
active_positions = Gauge('active_positions', 'Number of active trading positions', ['symbol'])

# Trading metrics
trades_total = Counter('trades_total', 'Total number of trades', ['user_id', 'symbol', 'side', 'status'])
trade_pnl = Histogram('trade_pnl', 'Trade P&L distribution', ['user_id', 'symbol'])
position_duration = Histogram('position_duration_seconds', 'Position duration in seconds', ['symbol'])

# API metrics
api_requests_total = Counter('api_requests_total', 'Total API requests', ['endpoint', 'method', 'status'])
api_request_duration = Histogram('api_request_duration_seconds', 'API request duration', ['endpoint'])

# System metrics
websocket_connections = Gauge('websocket_connections', 'Active WebSocket connections')
websocket_reconnections = Counter('websocket_reconnections_total', 'WebSocket reconnection attempts', ['user_id'])

# Error metrics
errors_total = Counter('errors_total', 'Total errors', ['error_type', 'component'])
binance_api_errors = Counter('binance_api_errors_total', 'Binance API errors', ['error_code'])

class MetricsCollector:
    """
    Metrics toplama ve yönetimi için yardımcı sınıf
    """
    
    @staticmethod
    def record_bot_start(user_id: str, symbol: str):
        """Bot başlatma metriği"""
        bot_starts_total.labels(user_id=user_id, symbol=symbol).inc()
        logger.info("Bot start recorded", user_id=user_id, symbol=symbol)
    
    @staticmethod
    def record_bot_stop(user_id: str, symbol: str, reason: str = "manual"):
        """Bot durdurma metriği"""
        bot_stops_total.labels(user_id=user_id, symbol=symbol, reason=reason).inc()
        logger.info("Bot stop recorded", user_id=user_id, symbol=symbol, reason=reason)
    
    @staticmethod
    def update_active_bots(count: int):
        """Aktif bot sayısını güncelle"""
        active_bots.set(count)
    
    @staticmethod
    def record_trade(user_id: str, symbol: str, side: str, pnl: float, status: str = "completed"):
        """Trade metriği kaydet"""
        trades_total.labels(user_id=user_id, symbol=symbol, side=side, status=status).inc()
        trade_pnl.labels(user_id=user_id, symbol=symbol).observe(pnl)
        logger.info("Trade recorded", user_id=user_id, symbol=symbol, side=side, pnl=pnl)
    
    @staticmethod
    def record_api_request(endpoint: str, method: str, status_code: int, duration: float):
        """API request metriği"""
        api_requests_total.labels(endpoint=endpoint, method=method, status=str(status_code)).inc()
        api_request_duration.labels(endpoint=endpoint).observe(duration)
    
    @staticmethod
    def record_error(error_type: str, component: str):
        """Hata metriği"""
        errors_total.labels(error_type=error_type, component=component).inc()
        logger.error("Error recorded", error_type=error_type, component=component)
    
    @staticmethod
    def record_binance_error(error_code: str):
        """Binance API hata metriği"""
        binance_api_errors.labels(error_code=error_code).inc()
    
    @staticmethod
    def update_websocket_connections(count: int):
        """WebSocket bağlantı sayısını güncelle"""
        websocket_connections.set(count)
    
    @staticmethod
    def record_websocket_reconnection(user_id: str):
        """WebSocket yeniden bağlanma metriği"""
        websocket_reconnections.labels(user_id=user_id).inc()

# Global metrics collector instance
metrics = MetricsCollector()

def get_metrics_data() -> str:
    """
    Prometheus formatında metrics data döndür
    """
    return generate_latest()

def get_metrics_content_type() -> str:
    """
    Prometheus metrics content type
    """
    return CONTENT_TYPE_LATEST