import structlog
import logging
import sys
import os
from datetime import datetime
from typing import Any, Dict

def setup_logging():
    """
    Structured logging konfigürasyonu - Render.com için optimize edilmiş
    """
    # Environment kontrol et
    environment = os.getenv("ENVIRONMENT", "PRODUCTION")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Timestamper processor
    def add_timestamp(logger, method_name, event_dict):
        event_dict["timestamp"] = datetime.utcnow().isoformat()
        return event_dict

    # Production için basit formatter
    def simple_formatter(logger, method_name, event_dict):
        if environment == "PRODUCTION":
            # Render.com için optimize edilmiş format
            level = event_dict.get('level', 'info').upper()
            message = event_dict.get('event', '')
            timestamp = event_dict.get('timestamp', datetime.utcnow().isoformat())
            
            # Ana mesaj
            log_parts = [f"[{level}]", message]
            
            # Ek bilgiler varsa ekle
            extra_info = []
            for key, value in event_dict.items():
                if key not in ['level', 'event', 'timestamp', 'logger']:
                    extra_info.append(f"{key}={value}")
            
            if extra_info:
                log_parts.append(" | ".join(extra_info))
            
            return " - ".join(log_parts)
        else:
            # Development için JSON
            return event_dict

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_timestamp,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Production'da basit format, development'ta JSON
    if environment == "PRODUCTION":
        processors.append(simple_formatter)
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging - Render.com için optimize edilmiş
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if environment == "PRODUCTION":
        # Production'da daha basit format
        log_format = "%(levelname)s - %(name)s - %(message)s"

    logging.basicConfig(
        format=log_format,
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
        force=True  # Mevcut config'i override et
    )
    
    # Bazı kütüphanelerin log seviyesini düşür
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("gunicorn").setLevel(logging.WARNING)
    
    # Redis connection hatalarını sustur
    logging.getLogger("redis").setLevel(logging.ERROR)

def get_logger(name: str = None):
    """
    Structured logger instance döndürür
    """
    # İlk çağrıda setup'ı çalıştır
    if not hasattr(get_logger, '_setup_done'):
        setup_logging()
        get_logger._setup_done = True
    
    return structlog.get_logger(name)

# Error handling için güvenli logger
class SafeLogger:
    def __init__(self, name: str):
        self.name = name
        try:
            self.logger = get_logger(name)
        except Exception:
            # Fallback to standard logging
            self.logger = logging.getLogger(name)
    
    def info(self, message, **kwargs):
        try:
            if hasattr(self.logger, 'info'):
                if kwargs:
                    self.logger.info(message, **kwargs)
                else:
                    self.logger.info(message)
        except Exception:
            print(f"INFO - {self.name} - {message}")
    
    def error(self, message, **kwargs):
        try:
            if hasattr(self.logger, 'error'):
                if kwargs:
                    self.logger.error(message, **kwargs)
                else:
                    self.logger.error(message)
        except Exception:
            print(f"ERROR - {self.name} - {message}")
    
    def warning(self, message, **kwargs):
        try:
            if hasattr(self.logger, 'warning'):
                if kwargs:
                    self.logger.warning(message, **kwargs)
                else:
                    self.logger.warning(message)
        except Exception:
            print(f"WARNING - {self.name} - {message}")
    
    def debug(self, message, **kwargs):
        try:
            if hasattr(self.logger, 'debug'):
                if kwargs:
                    self.logger.debug(message, **kwargs)
                else:
                    self.logger.debug(message)
        except Exception:
            # Debug mesajlarını production'da gösterme
            if os.getenv("ENVIRONMENT") != "PRODUCTION":
                print(f"DEBUG - {self.name} - {message}")
    
    def critical(self, message, **kwargs):
        try:
            if hasattr(self.logger, 'critical'):
                if kwargs:
                    self.logger.critical(message, **kwargs)
                else:
                    self.logger.critical(message)
        except Exception:
            print(f"CRITICAL - {self.name} - {message}")

# Güvenli logger factory
def get_safe_logger(name: str = None):
    """
    Hata durumunda bile çalışan güvenli logger döndürür
    """
    return SafeLogger(name or "ezyago_trading")

# Global logger instance - güvenli versiyonu kullan
logger = get_safe_logger("ezyago_trading")

# Auto-setup on import
try:
    setup_logging()
except Exception as e:
    # Fallback logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout
    )
    print(f"Warning: Advanced logging setup failed, using basic logging: {e}")
