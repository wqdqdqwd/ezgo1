import structlog
import logging
import sys
from datetime import datetime
from typing import Any, Dict

def setup_logging():
    """
    Structured logging konfigürasyonu
    """
    # Timestamper processor
    def add_timestamp(logger, method_name, event_dict):
        event_dict["timestamp"] = datetime.utcnow().isoformat()
        return event_dict

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            add_timestamp,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

def get_logger(name: str = None):
    """
    Structured logger instance döndürür
    """
    return structlog.get_logger(name)

# Global logger instance
logger = get_logger("ezyago_trading")