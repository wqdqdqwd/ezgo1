from pydantic import BaseModel, validator, Field
from typing import Optional, List
import re
from app.utils.logger import get_logger

logger = get_logger("validation")

class TradingSymbolValidator:
    """
    Trading symbol validation
    """
    VALID_SYMBOLS = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT',
        'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT',
        'LTCUSDT', 'LINKUSDT', 'UNIUSDT', 'ATOMUSDT', 'FILUSDT'
    ]
    
    @classmethod
    def validate_symbol(cls, symbol: str) -> bool:
        """Symbol validation"""
        if not symbol or not isinstance(symbol, str):
            return False
        
        symbol = symbol.upper().strip()
        
        # Basic format check
        if not re.match(r'^[A-Z]{3,10}USDT$', symbol):
            return False
        
        # Whitelist check (optional - can be removed for more flexibility)
        return symbol in cls.VALID_SYMBOLS

class TradingParametersValidator:
    """
    Trading parameters validation
    """
    
    @staticmethod
    def validate_leverage(leverage: int) -> bool:
        """Leverage validation"""
        return isinstance(leverage, int) and 1 <= leverage <= 125
    
    @staticmethod
    def validate_order_size(order_size: float) -> bool:
        """Order size validation"""
        return isinstance(order_size, (int, float)) and 10 <= order_size <= 10000
    
    @staticmethod
    def validate_percentage(percentage: float, min_val: float = 0.1, max_val: float = 50.0) -> bool:
        """Percentage validation (for TP/SL)"""
        return isinstance(percentage, (int, float)) and min_val <= percentage <= max_val
    
    @staticmethod
    def validate_timeframe(timeframe: str) -> bool:
        """Timeframe validation"""
        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']
        return timeframe in valid_timeframes

class ApiKeyValidator:
    """
    API key validation
    """
    
    @staticmethod
    def validate_binance_api_key(api_key: str) -> bool:
        """Binance API key format validation"""
        if not api_key or not isinstance(api_key, str):
            return False
        
        # Binance API keys are typically 64 characters long
        api_key = api_key.strip()
        return len(api_key) == 64 and api_key.isalnum()
    
    @staticmethod
    def validate_binance_secret(secret: str) -> bool:
        """Binance API secret format validation"""
        if not secret or not isinstance(secret, str):
            return False
        
        # Binance API secrets are typically 64 characters long
        secret = secret.strip()
        return len(secret) == 64 and secret.isalnum()

# Pydantic v1 compatible models
class EnhancedStartRequest(BaseModel):
    """
    Enhanced start request with comprehensive validation
    """
    symbol: str = Field(..., min_length=6, max_length=12)
    timeframe: str = Field(..., min_length=2, max_length=3)
    leverage: int = Field(..., ge=1, le=125)
    order_size: float = Field(..., ge=10, le=10000)
    stop_loss: float = Field(..., ge=0.1, le=50.0)
    take_profit: float = Field(..., ge=0.1, le=50.0)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not TradingSymbolValidator.validate_symbol(v):
            raise ValueError('Invalid trading symbol')
        return v.upper().strip()
    
    @validator('timeframe')
    def validate_timeframe(cls, v):
        if not TradingParametersValidator.validate_timeframe(v):
            raise ValueError('Invalid timeframe')
        return v
    
    @validator('take_profit')
    def validate_tp_greater_than_sl(cls, v, values):
        if 'stop_loss' in values and v <= values['stop_loss']:
            raise ValueError('Take profit must be greater than stop loss')
        return v

class EnhancedApiKeysRequest(BaseModel):
    """
    Enhanced API keys request with validation
    """
    api_key: str = Field(..., min_length=60, max_length=70)
    api_secret: str = Field(..., min_length=60, max_length=70)
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not ApiKeyValidator.validate_binance_api_key(v):
            raise ValueError('Invalid Binance API key format')
        return v.strip()
    
    @validator('api_secret')
    def validate_api_secret(cls, v):
        if not ApiKeyValidator.validate_binance_secret(v):
            raise ValueError('Invalid Binance API secret format')
        return v.strip()

def sanitize_string(input_str: str, max_length: int = 100) -> str:
    """
    String sanitization
    """
    if not isinstance(input_str, str):
        return ""
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\';\\]', '', input_str)
    
    # Limit length
    sanitized = sanitized[:max_length]
    
    return sanitized.strip()

def validate_user_input(data: dict) -> dict:
    """
    Generic user input validation
    """
    validated_data = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            validated_data[key] = sanitize_string(value)
        elif isinstance(value, (int, float)):
            # Numeric validation
            if -1000000 <= value <= 1000000:  # Reasonable bounds
                validated_data[key] = value
            else:
                logger.warning(f"Numeric value out of bounds: {key}={value}")
                validated_data[key] = 0
        else:
            validated_data[key] = value
    
    return validated_data
