from datetime import datetime, timezone
from typing import Dict, Any
import json

class MetricsCollector:
    """Basit metrics kolektörü"""
    
    def __init__(self):
        self.data = {
            "api_requests": 0,
            "bot_starts": 0,
            "bot_stops": 0,
            "trades": 0,
            "errors": 0,
            "websocket_connections": 0,
            "websocket_reconnections": 0,
            "last_update": datetime.now(timezone.utc).isoformat()
        }
        
    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """API isteği kaydeder"""
        self.data["api_requests"] += 1
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        
    def record_bot_start(self, user_id: str, symbol: str):
        """Bot başlatma kaydeder"""
        self.data["bot_starts"] += 1
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        
    def record_bot_stop(self, user_id: str, symbol: str, reason: str):
        """Bot durdurma kaydeder"""
        self.data["bot_stops"] += 1
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        
    def record_trade(self, user_id: str, symbol: str, side: str, pnl: float, reason: str):
        """Trade kaydeder"""
        self.data["trades"] += 1
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        
    def record_error(self, error_type: str, component: str):
        """Hata kaydeder"""
        self.data["errors"] += 1
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        
    def update_websocket_connections(self, count: int):
        """WebSocket bağlantı sayısını günceller"""
        self.data["websocket_connections"] = count
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        
    def record_websocket_reconnection(self, user_id: str):
        """WebSocket yeniden bağlanma kaydeder"""
        self.data["websocket_reconnections"] += 1
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        
    def record_binance_error(self, error_code: str):
        """Binance API hatası kaydeder"""
        self.record_error(f"binance_{error_code}", "binance_client")

# Global metrics instance
metrics = MetricsCollector()

def get_metrics_data() -> str:
    """Metrics verilerini Prometheus formatında döndürür"""
    data = metrics.data
    prometheus_format = f"""
# HELP api_requests_total Total API requests
# TYPE api_requests_total counter
api_requests_total {data['api_requests']}

# HELP bot_starts_total Total bot starts
# TYPE bot_starts_total counter
bot_starts_total {data['bot_starts']}

# HELP bot_stops_total Total bot stops
# TYPE bot_stops_total counter
bot_stops_total {data['bot_stops']}

# HELP trades_total Total trades
# TYPE trades_total counter
trades_total {data['trades']}

# HELP errors_total Total errors
# TYPE errors_total counter
errors_total {data['errors']}

# HELP websocket_connections Current WebSocket connections
# TYPE websocket_connections gauge
websocket_connections {data['websocket_connections']}

# HELP websocket_reconnections_total Total WebSocket reconnections
# TYPE websocket_reconnections_total counter
websocket_reconnections_total {data['websocket_reconnections']}
"""
    return prometheus_format.strip()

def get_metrics_content_type() -> str:
    """Metrics content type döndürür"""
    return "text/plain; version=0.0.4; charset=utf-8"
